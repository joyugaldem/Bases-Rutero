#!/usr/bin/env python3
"""
Recrea todos los stored procedures, triggers y funciones
en la base de datos actual. Útil tras corregir bootstrap_db.py.
No modifica datos existentes (tablas, filas).
Uso: python scripts/recreate_stored_procs.py
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


def get_connection():
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


def split_statements(filename, content):
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
        lines = []
        for line in content.splitlines():
            stripped = re.sub(r"--.*$", "", line).strip()
            if stripped:
                lines.append(stripped)
        sql = "\n".join(lines)
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
        return [t for t in tokens if not t.upper().startswith("USE ")
                                         and not t.upper().startswith("SET NAMES")]


def run():
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
    print(f"Procedures/triggers originales eliminados.")

    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    sql_files = sorted(glob.glob(os.path.join(sql_dir, "*.sql")))
    total = 0
    for sql_path in sql_files:
        name = os.path.basename(sql_path)
        if name not in DELIMITER_FILES:
            continue
        print(f"\n→ {name}")
        with open(sql_path, encoding="utf-8") as f:
            content = f.read()
        stmts = split_statements(sql_path, content)
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
