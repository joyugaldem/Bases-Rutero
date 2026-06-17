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


def query(sql, params=None, fetchone=False):
    """Ejecuta una consulta SELECT y retorna los resultados como lista de dicts."""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    rows = cur.fetchone() if fetchone else cur.fetchall()
    cur.close()
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


def execute(sql, params=None):
    """Ejecuta INSERT/UPDATE/DELETE y hace commit."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
