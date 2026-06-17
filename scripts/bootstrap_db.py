#!/usr/bin/env python3
"""
Bootstrap script para inicializar lacteosdb desde los archivos sql/.
Ejecuta 01_schema.sql → 08_datos_prueba.sql en orden.
Solo corre si la base de datos esta vacia (sin tablas).
Uso: python bootstrap_db.py
"""

import os
import sys
import re
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import mysql.connector


DELIMITER_FILES = {"02_crud.sql", "03_transacciones.sql", "05_triggers.sql",
                   "06_cursores.sql", "07_consultas_avanzadas.sql"}


def strip_comments(sql):
    """Elimina comentarios de linea (--) y de bloque aunque esten dentro de strings."""
    lines = []
    for line in sql.splitlines():
        stripped = re.sub(r"--.*$", "", line).strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def split_statements(filename, content):
    """
    Divide el contenido de un archivo .sql en sentencias ejecutables.
    - Archivos con DELIMITER //: split por '//' (cada bloque es un statement).
    - Archivos normales: split por ';' a nivel de tokens.
    Retorna lista de strings no vacios.
    """
    name = os.path.basename(filename)

    if name in DELIMITER_FILES:
        parts = content.split("//")
        statements = []
        for part in parts:
            lines = part.splitlines()
            cleaned_lines = []
            for line in lines:
                l = line.strip()
                if l.upper().startswith("DELIMITER"):
                    continue
                cleaned_lines.append(line)
            stmt = "\n".join(cleaned_lines).strip()
            if stmt:
                statements.append(stmt)
        return statements
    else:
        sql = strip_comments(content)
        tokens = []
        buffer = []
        in_string = False
        string_char = None

        i = 0
        while i < len(sql):
            c = sql[i]
            if not in_string and c in ("'", '"'):
                in_string = True
                string_char = c
                buffer.append(c)
            elif in_string and c == string_char and (i + 1 >= len(sql) or sql[i + 1] != string_char):
                in_string = False
                string_char = None
                buffer.append(c)
            elif not in_string and c == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
                buffer.append("''")
                i += 1
            elif not in_string and c == ';':
                token = "".join(buffer).strip()
                if token:
                    tokens.append(token)
                buffer = []
            else:
                buffer.append(c)
            i += 1

        tail = "".join(buffer).strip()
        if tail:
            tokens.append(tail)

        result = []
        for t in tokens:
            t = t.strip()
            if t.upper().startswith("USE ") or not t:
                continue
            result.append(t)
        return result


def get_connection():
    kwargs = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
        "charset": "utf8mb4",
        "autocommit": False,
    }
    if config.DB_NAME:
        kwargs["database"] = config.DB_NAME
    return mysql.connector.connect(**kwargs)


def is_initialized(conn):
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    cur.close()
    return len(tables) > 0


def run_bootstrap():
    conn = get_connection()

    if is_initialized(conn):
        print("lacteosdb ya tiene tablas. Bootstrapping omitido.")
        conn.close()
        return

    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    sql_files = sorted(glob.glob(os.path.join(sql_dir, "*.sql")))

    total_stmts = 0
    for sql_path in sql_files:
        name = os.path.basename(sql_path)
        print(f"\n→ {name}")
        with open(sql_path, encoding="utf-8") as f:
            content = f.read()

        statements = split_statements(sql_path, content)
        cur = conn.cursor()
        ok, fail = 0, 0

        for stmt in statements:
            if not stmt.strip():
                continue
            try:
                cur.execute(stmt)
                while True:
                    try:
                        cur.fetchall()
                    except mysql.connector.Error:
                        pass
                    if not cur.nextset():
                        break
                conn.commit()
                ok += 1
            except mysql.connector.Error as e:
                fail += 1
                err = str(e)
                if "Duplicate" in err or "database exists" in err.lower():
                    pass
                else:
                    print(f"   [!] {stmt[:80]}… → {err[:120]}")
        cur.close()
        total_stmts += ok
        print(f"   {ok} ok, {fail} errores")

    conn.close()
    print(f"\nBootstrap completo. {total_stmts} sentencias ejecutadas.")


if __name__ == "__main__":
    run_bootstrap()
