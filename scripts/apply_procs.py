"""Apply all SQL files to Railway MySQL. Reads connection from environment variables.

Uso con Railway:
  railway run python scripts/apply_procs.py

Variables requeridas (APPLY_DB_* tienen prioridad, luego cae a DB_*):
  APPLY_DB_HOST, APPLY_DB_PORT, APPLY_DB_USER, APPLY_DB_PASSWORD, APPLY_DB_NAME
  o bien las variables DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME del servicio.
"""
import glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector
from sql_parser import split_sql

HOST     = os.environ.get("APPLY_DB_HOST")     or os.environ.get("DB_HOST",     "localhost")
PORT     = int(os.environ.get("APPLY_DB_PORT") or os.environ.get("DB_PORT",     3306))
USER     = os.environ.get("APPLY_DB_USER")     or os.environ.get("DB_USER",     "root")
PASSWORD = os.environ.get("APPLY_DB_PASSWORD") or os.environ.get("DB_PASSWORD", "")
DB       = os.environ.get("APPLY_DB_NAME")     or os.environ.get("DB_NAME",     "railway")

if not HOST or HOST == "localhost" and not os.environ.get("DB_HOST"):
    sys.exit("ERROR: Defina APPLY_DB_HOST o DB_HOST con el host de la base de datos.")


def main():
    """Aplica todos los archivos `sql/*.sql` al destino configurado.

    Pensado para deploy a Railway (o cualquier MySQL remoto) usando las
    variables `APPLY_DB_*` con fallback a `DB_*`. A diferencia de
    `bootstrap_db.py`, aquí se ejecuta contra una BD que se asume ya
    creada y vacía de lógica (o con lógica previa que se sobreescribe).

    Diferencias clave vs. bootstrap_db:
        - Conexión con `autocommit=True` (no hay transacciones largas).
        - Lee `APPLY_DB_*` primero, luego `DB_*`, luego defaults.
        - No skipea si hay tablas: la idea es "aplicar otra vez" los
          archivos, sobrescribiendo SPs, vistas, etc.

    Errores tolerados (skip silencioso):
        - "already exists" / "duplicate" / "database exists".

    Uso típico con Railway:
        $ railway run python scripts/apply_procs.py
    """
    conn = mysql.connector.connect(
        host=HOST, port=PORT, user=USER, password=PASSWORD,
        database=DB, charset="utf8mb4", autocommit=True
    )

    sql_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
    files = sorted(glob.glob(os.path.join(sql_dir, "*.sql")))
    total = 0

    for f in files:
        name = os.path.basename(f)
        print(f"\n-> {name}")
        with open(f, encoding="utf-8") as fh:
            content = fh.read()

        stmts = split_sql(content)
        ok = fail = skip = 0
        cur = conn.cursor()
        for s in stmts:
            if not s.strip():
                continue
            try:
                cur.execute(s)
                try:
                    cur.fetchall()
                except Exception:
                    pass
                while cur.nextset():
                    try:
                        cur.fetchall()
                    except Exception:
                        pass
                ok += 1
            except mysql.connector.Error as e:
                err = str(e)
                if ("already exists" in err.lower() or "duplicate" in err.lower()
                        or "database exists" in err.lower()):
                    skip += 1
                else:
                    fail += 1
                    print(f"   [!] {s[:80].strip()}... -> {err[:120]}")
        cur.close()
        total += ok
        print(f"   {ok} ok, {skip} skip, {fail} errores")

    conn.close()
    print(f"\nCompleto. {total} sentencias ejecutadas.")


if __name__ == "__main__":
    main()
