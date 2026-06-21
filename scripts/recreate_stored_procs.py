#!/usr/bin/env python3
"""
Recrea todos los stored procedures, triggers y funciones
en la base de datos actual. Útil tras corregir bootstrap_db.py.
No modifica datos existentes (tablas, filas).
Uso: python scripts/recreate_stored_procs.py
"""

import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import mysql.connector
from sql_parser import split_statements


# Archivos que contienen stored procedures, triggers o cursores
# (los únicos donde este script necesita re-aplicar SQL)
PROC_FILES = {"02_crud.sql", "03_transacciones.sql", "05_triggers.sql",
              "06_cursores.sql", "07_consultas_avanzadas.sql"}


def get_connection():
    """Abre una conexión MySQL usando la configuración de `config.py`.

    Equivalente a `bootstrap_db.get_connection()` pero intencionalmente
    incluye siempre `database=config.DB_NAME` porque aquí ya asumimos
    que la BD existe (no es bootstrap inicial).

    Returns:
        mysql.connector.connection.MySQLConnection: conexión lista
        con `autocommit=False` para controlar transacciones.
    """
    kwargs = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
        "charset": "utf8mb4",
        "database": config.DB_NAME,
        "autocommit": False,
    }
    return mysql.connector.connect(**kwargs)


def run():
    """Recrea procedures, triggers y SPs sin tocar datos.

    Flujo:
        1. DROP de todos los procedures y triggers existentes en el
           schema actual (consultando `information_schema`).
        2. Recorre los archivos SQL en `sql/` y reaplica solo los que
           están en `PROC_FILES` (los que definen lógica, no schema
           ni datos).
        3. Commit por sentencia para que un fallo no bloquee las demás.

    Use este script cuando:
        - Modificás un stored procedure en `sql/02_crud.sql` o
          `sql/03_transacciones.sql` y querés propagar el cambio sin
          re-bootstrap (que sí borra datos).
        - Tras un fix en bootstrap_db.py, para alinear los SPs ya
          desplegados con la versión nueva.

    Notes:
        - No toca `01_schema.sql`, `04_vistas.sql` ni `08_datos_prueba.sql`.
        - Si un DROP falla (permisos, FK referenciando) se ignora y se
          continúa: el CREATE posterior puede sobrescribir de todos modos.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Drop existing procedures and triggers first
    cur.execute("""
        SELECT CONCAT('DROP PROCEDURE IF EXISTS ', ROUTINE_NAME, ';;')
        FROM information_schema.ROUTINES
        WHERE ROUTINE_SCHEMA = %s AND ROUTINE_TYPE = 'PROCEDURE'
    """, (config.DB_NAME,))
    drops = [row[0] for row in cur.fetchall()]
    for d in drops:
        try:
            cur.execute(d)
        except mysql.connector.Error:
            pass

    cur.execute("""
        SELECT CONCAT('DROP TRIGGER IF EXISTS ', TRIGGER_NAME, ';;')
        FROM information_schema.TRIGGERS
        WHERE TRIGGER_SCHEMA = %s
    """, (config.DB_NAME,))
    drops = [row[0] for row in cur.fetchall()]
    for d in drops:
        try:
            cur.execute(d)
        except mysql.connector.Error:
            pass

    conn.commit()
    print("Procedures/triggers originales eliminados.")

    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    sql_files = sorted(glob.glob(os.path.join(sql_dir, "*.sql")))
    total = 0
    for sql_path in sql_files:
        name = os.path.basename(sql_path)
        if name not in PROC_FILES:
            continue
        print(f"\n→ {name}")
        with open(sql_path, encoding="utf-8") as f:
            content = f.read()
        stmts = split_statements(name, content)
        ok, fail = 0, 0
        for stmt in stmts:
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
                print(f"   [!] {stmt[:60]}… → {e}")
        print(f"   {ok} ok, {fail} errores")
        total += ok

    cur.close()
    conn.close()
    print(f"\nListo. {total} procedimientos/triggers recreados.")
    print("Los datos existentes (tablas, filas) no fueron modificados.")


if __name__ == "__main__":
    run()
