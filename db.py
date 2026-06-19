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
    """Retorna la conexión activa para la solicitud actual."""
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
    """Cierra la conexión al final de cada solicitud."""
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def query(sql, params=None, fetchone=False, default=None):
    """Ejecuta una consulta SELECT y retorna los resultados como lista de dicts.

    Si fetchone=True y no hay filas, retorna `default` (None por defecto) en
    lugar de propagar la excepción o devolver un dict vacío.
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
    """
    Llama a un stored procedure y retorna todos los result sets.
    Los parámetros OUT deben incluirse en args como None.
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
    """
    Llama a un stored procedure y retorna su primer result set como una
    lista plana de diccionarios.

    Conveniencia para el caso común `results[0] if results else []`.
    Si first=False, retorna la lista de result sets completa (igual que
    call_proc).
    """
    results = call_proc(proc_name, args)
    if first:
        return results[0] if results else []
    return results


def call_proc_out(proc_name, args):
    """
    Llama a un stored procedure con parámetros OUT.
    Retorna (result_sets, out_args) donde out_args son los valores de salida.
    args debe ser una lista mutable.
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
    """
    Llama un stored procedure con IN args conocidos y OUT params nombrados.

    in_args:    lista de valores para parámetros IN (en orden).
    out_names:  lista de nombres simbólicos para los OUT (en orden).

    Retorna (results, dict) donde dict mapea cada out_name a su valor
    retornado por el SP. Útil para evitar acceso por índice posicional
    frágil (out[10], out[12], etc.).
    """
    full_args = list(in_args) + [None] * len(out_names)
    results, out_args = call_proc_out(proc_name, full_args)
    out_values = out_args[len(in_args):]
    return results, dict(zip(out_names, out_values))


def execute(sql, params=None):
    """Ejecuta INSERT/UPDATE/DELETE y hace commit."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
