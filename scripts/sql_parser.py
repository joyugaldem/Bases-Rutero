"""
Parser SQL compartido para los scripts de gestión de base de datos.

Provee una sola implementación de cómo dividir un archivo .sql en sentencias
ejecutables, con manejo correcto de la directiva DELIMITER (necesaria para
los stored procedures que contienen `;` internos) y filtrado consistente
de sentencias que no deben ejecutarse contra el servidor de aplicación
(USE, SET NAMES).

Reemplaza las 3 implementaciones divergentes que existían en:
  - scripts/bootstrap_db.py
  - scripts/recreate_stored_procs.py
  - scripts/apply_procs.py

Mejoras sobre las versiones anteriores:
  - Filtra USE y SET NAMES consistentemente (bug preexistente en
    bootstrap_db.py que causaba que las tablas se crearan en `lacteosdb`
    en lugar de en el DB_NAME configurado por env)
  - Estado unificado: una sola función, no hardcodea una lista de
    "DELIMITER files" (esa distinción la hace cada script que llama)
  - Tolerante a comentarios de línea (--) y de bloque (/* */), tanto
    a nivel de línea completa como inline
  - Comentarios inline NO interfieren con la detección de delimitador
    (e.g. `SELECT 1; -- fin` cierra la sentencia)
"""

import re


# Sentencias que filtramos a nivel de archivo completo cuando aparecen
# como sentencias top-level (no afectan la lógica del schema).
_RE_DELIMITER = re.compile(r"^DELIMITER\s+(\S+)\s*$", re.IGNORECASE)
_RE_LINE_COMMENT = re.compile(r"--.*$")
_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_FILTERED = re.compile(r"^(USE|SET\s+NAMES)\b", re.IGNORECASE)


def _strip_inline_comments(line: str) -> str:
    """Elimina comentarios inline (de línea y de bloque) de una línea.

    Útil para detectar delimitadores sin que un comentario al final
    (`SELECT 1; -- fin`) oculte el `;`.
    """
    return _RE_BLOCK_COMMENT.sub("", _RE_LINE_COMMENT.sub("", line))


def _is_filtered(stmt: str) -> bool:
    """True si la sentencia no debe ejecutarse (USE, SET NAMES)."""
    if not stmt:
        return True
    cleaned = _strip_inline_comments(stmt).strip()
    return bool(cleaned) and bool(_RE_FILTERED.match(cleaned))


def split_sql(content: str) -> list:
    """Divide el contenido de un archivo .sql en sentencias ejecutables.

    Maneja correctamente la directiva DELIMITER // usada para escribir
    stored procedures con `;` internos. Filtra sentencias USE y SET NAMES
    para que el script sea portable entre bases de datos.

    Args:
        content: contenido completo del archivo .sql

    Returns:
        Lista de sentencias SQL ejecutables, sin USE/SET NAMES, sin
        sentencias vacías.
    """
    delimiter = ";"
    statements: list = []
    current_lines: list = []

    for line in content.splitlines():
        # Cambio de delimitador: `DELIMITER //`, `DELIMITER $`, etc.
        m = _RE_DELIMITER.match(line.strip())
        if m:
            delimiter = m.group(1)
            continue

        # Líneas vacías, comentarios de línea, o líneas que son SOLO
        # un comentario de bloque (`/* hola */`): las descartamos
        # (excepto que ya estemos acumulando una sentencia)
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or not _strip_inline_comments(line).strip():
            if current_lines:
                current_lines.append(line)
            continue

        current_lines.append(line)

        # Detección de fin de sentencia: usamos una vista de la línea
        # sin comentarios inline, para que `SELECT 1; -- fin` cierre.
        line_no_comments = _strip_inline_comments(line).strip()
        if line_no_comments.endswith(delimiter):
            stmt = "\n".join(current_lines).rstrip()
            # Cortar el delimitador al final
            stripped_stmt = _strip_inline_comments(stmt).rstrip()
            if stripped_stmt.endswith(delimiter):
                idx = stmt.rfind(delimiter)
                stmt = stmt[:idx].rstrip()
            if not _is_filtered(stmt):
                statements.append(stmt)
            current_lines = []

    # Flush: si quedó algo sin delimitador final (ej. archivo sin ';' al
    # final), lo agregamos de todas formas
    if current_lines:
        stmt = "\n".join(current_lines).strip()
        if not _is_filtered(stmt):
            statements.append(stmt)

    return statements


def split_statements(filename: str, content: str) -> list:
    """Wrapper retrocompatible con la API usada por bootstrap_db.py y
    recreate_stored_procs.py.

    El nombre del archivo ya no es necesario (la lógica es la misma para
    todos), pero se mantiene para no romper los call sites existentes.

    Args:
        filename: ruta del archivo (ignorada, solo para compatibilidad)
        content: contenido del archivo

    Returns:
        Lista de sentencias ejecutables.
    """
    return split_sql(content)

