"""
Módulo de acceso a la base de datos.
Provee una conexión MySQL por solicitud y helpers para
llamar stored procedures y ejecutar queries.
"""

import logging
import mysql.connector
from flask import g
import config

logger = logging.getLogger(__name__)


def get_db():
    """Obtiene (o crea) la conexión MySQL asociada a la solicitud actual.

    Flask guarda la conexión en `flask.g` para que una misma solicitud
    reutilice la misma instancia a lo largo de varias llamadas. Si no
    existe, abre una nueva con la configuración de `config.py` y aplica
    `SET NAMES utf8mb4` para asegurar la codificación en la sesión.

    Returns:
        mysql.connector.connection.MySQLConnection: conexión activa.

    Notes:
        `autocommit=False`: cada helper decide cuándo hacer commit
        (transacciones explícitas en stored procedures o `execute()`).
    """
    if "db" not in g:
        conn = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=False,
        )
        cur = conn.cursor()
        cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.close()
        g.db = conn
    return g.db


def close_db(e=None):
    """Cierra la conexión MySQL al final de la solicitud Flask.

    Se registra como `teardown_appcontext` en `app.py`, por lo que Flask
    la invoca automáticamente al terminar cada request (con o sin
    excepción). Es seguro llamarla incluso si la conexión nunca se
    abrió (`g.db` puede no existir).

    Args:
        e: excepción no manejada (provista por Flask; no se usa aquí,
           el rollback se maneja dentro de cada helper).
    """
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def query(sql, params=None, fetchone=False, default=None):
    """Ejecuta un SELECT directo y devuelve los resultados como dicts.

    Pensado para consultas parametrizadas simples (SELECTs que el sistema
    no modela como stored procedure, ej.: estadísticas del dashboard).
    Para toda la lógica de negocio se prefiere `call_proc*`.

    Args:
        sql: sentencia SELECT con placeholders `%s`.
        params: tupla/lista de parámetros a enlazar.
        fetchone: si True, devuelve solo la primera fila.
        default: valor retornado cuando no hay filas y `fetchone=True`.

    Returns:
        list[dict] | dict | default: filas como diccionarios
        (columna -> valor). Cursor usa `dictionary=True`.

    Raises:
        mysql.connector.Error: errores de SQL o de conexión.
    """
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    rows = cur.fetchone() if fetchone else cur.fetchall()
    cur.close()
    if rows is None:
        return default
    return rows


def call_proc(proc_name, args=()):
    """Llama a un stored procedure y devuelve todos sus result sets.

    Pensado para SPs sin parámetros OUT o cuando no se necesita leer
    los OUT (ej.: `sp_consultar_productos`). Para SPs con OUT usar
    `call_proc_named`.

    Args:
        proc_name: nombre del stored procedure.
        args: tupla/lista de argumentos. Los OUT deben ir como None
              en la posición correspondiente.

    Returns:
        list[list[dict]]: lista de result sets; cada result set es una
        lista de filas como diccionarios.

    Notes:
        Hace `conn.commit()` siempre, incluso si el SP sólo lee. En SPs
        de sólo lectura es un commit vacío, pero simplifica el código
        al evitar condicionales.
    """
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.callproc(proc_name, args)
    results = []
    for rs in cur.stored_results():
        results.append(rs.fetchall())
    conn.commit()
    cur.close()
    return results


def call_proc_dict(proc_name, args=(), first=True):
    """Llama un SP y aplana el primer result set como lista de dicts.

    Atajo para el patrón `results[0] if results else []` que aparece en
    casi todos los endpoints de Flask.

    Args:
        proc_name: nombre del stored procedure.
        args: argumentos del SP.
        first: si True, devuelve solo el primer result set aplanado;
               si False, devuelve la lista completa de result sets.

    Returns:
        list[dict] | list[list[dict]]: según `first`.
    """
    results = call_proc(proc_name, args)
    if first:
        return results[0] if results else []
    return results


def call_proc_out(proc_name, args):
    """Llama un SP con parámetros OUT y devuelve sus valores.

    A diferencia de `call_proc`, aquí el cursor se crea sin
    `dictionary=True` para que `cur.callproc()` retorne la tupla con
    los valores OUT ya rellenados (el servidor los escribe en la misma
    lista `args` que se pasa por referencia).

    Args:
        proc_name: nombre del SP.
        args: lista mutable con los IN seguidos de None por cada OUT
              (la función agrega los None automáticamente al combinar
              con `call_proc_named`).

    Returns:
        tuple[list, list]: (result_sets, out_args). `out_args` contiene
        los valores de salida en el orden en que aparecen en el SP.

    Raises:
        Exception: cualquier error de MySQL. Se hace rollback antes de
        relanzar para no dejar la transacción a medias.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        out_args = cur.callproc(proc_name, args)
        results = []
        for rs in cur.stored_results():
            results.append(rs.fetchall())
        conn.commit()
        cur.close()
        return results, list(out_args)
    except Exception:
        logger.exception("call_proc_out(%s) failed", proc_name)
        conn.rollback()
        cur.close()
        raise


def call_proc_named(proc_name, in_args, out_names):
    """Llama un SP con IN explícitos y mapea los OUT a un diccionario.

    Elimina la fragilidad de acceder por posición (`out[10]`, `out[12]`)
    que rompe cuando el SP cambia el orden de sus parámetros. Los
    nombres simbólicos se mantienen en `constants.SP_OUT`.

    Args:
        proc_name: nombre del SP.
        in_args: lista de valores para los parámetros IN en orden.
        out_names: lista de nombres simbólicos para los OUT en orden
                   (debe coincidir con la firma del SP).

    Returns:
        tuple[list, dict]: (result_sets, dict_out). `dict_out` mapea
        cada nombre en `out_names` al valor devuelto por el SP.

    Example:
        >>> _, out = call_proc_named(
        ...     "sp_insertar_producto",
        ...     ["Leche", "L001", "Leche"],
        ...     SP_OUT["sp_insertar_producto"],  # ["id_producto"]
        ... )
        >>> out["id_producto"]
        42
    """
    full_args = list(in_args) + [None] * len(out_names)
    results, out_args = call_proc_out(proc_name, full_args)
    out_values = out_args[len(in_args):]
    return results, dict(zip(out_names, out_values))


def execute(sql, params=None):
    """Ejecuta un INSERT/UPDATE/DELETE directo y hace commit.

    Pensado para casos donde no hay stored procedure (ej.: seeds de
    pruebas en `tests/conftest.py`). En código de producción se prefiere
    `call_proc*`.

    Args:
        sql: sentencia con placeholders `%s`.
        params: tupla/lista de parámetros.

    Returns:
        int | None: `lastrowid` del INSERT (None si no aplica).

    Raises:
        mysql.connector.Error: errores de SQL. No se hace rollback
        automático: el caller debe manejarlo si la sentencia falla.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
