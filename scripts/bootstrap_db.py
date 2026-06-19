#!/usr/bin/env python3
"""
Bootstrap script para inicializar lacteosdb desde los archivos sql/.
Ejecuta 01_schema.sql → 08_datos_prueba.sql en orden.
Solo corre si la base de datos esta vacia (sin tablas).
Uso: python bootstrap_db.py
"""

import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import mysql.connector
from sql_parser import split_statements


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
        print(f"{config.DB_NAME} ya tiene tablas. Bootstrapping omitido.")
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

        statements = split_statements(name, content)
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
