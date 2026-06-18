"""Apply all SQL files to Railway MySQL. Reads connection from environment variables.

Uso con Railway:
  railway run python scripts/apply_procs.py

Variables requeridas (APPLY_DB_* tienen prioridad, luego cae a DB_*):
  APPLY_DB_HOST, APPLY_DB_PORT, APPLY_DB_USER, APPLY_DB_PASSWORD, APPLY_DB_NAME
  o bien las variables DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME del servicio.
"""
import re, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector

HOST     = os.environ.get("APPLY_DB_HOST")     or os.environ.get("DB_HOST",     "localhost")
PORT     = int(os.environ.get("APPLY_DB_PORT") or os.environ.get("DB_PORT",     3306))
USER     = os.environ.get("APPLY_DB_USER")     or os.environ.get("DB_USER",     "root")
PASSWORD = os.environ.get("APPLY_DB_PASSWORD") or os.environ.get("DB_PASSWORD", "")
DB       = os.environ.get("APPLY_DB_NAME")     or os.environ.get("DB_NAME",     "railway")

if not HOST or HOST == "localhost" and not os.environ.get("DB_HOST"):
    sys.exit("ERROR: Defina APPLY_DB_HOST o DB_HOST con el host de la base de datos.")


def split_sql(content):
    delimiter = ";"
    statements = []
    current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        m = re.match(r"^DELIMITER\s+(\S+)\s*$", stripped, re.IGNORECASE)
        if m:
            delimiter = m.group(1)
            continue
        if not stripped or stripped.startswith("--"):
            if current_lines:
                current_lines.append(line)
            continue
        current_lines.append(line)
        if stripped.endswith(delimiter):
            stmt = "\n".join(current_lines).rstrip()
            if stmt.endswith(delimiter):
                stmt = stmt[: -len(delimiter)].rstrip()
            clean = re.sub(r"--.*$", "", stmt, flags=re.MULTILINE).strip()
            clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL).strip()
            if clean and not re.match(r"^USE\b", clean, re.IGNORECASE):
                statements.append(stmt)
            current_lines = []

    if current_lines:
        stmt = "\n".join(current_lines).strip()
        clean = re.sub(r"--.*$", "", stmt, flags=re.MULTILINE).strip()
        if clean and not re.match(r"^USE\b", clean, re.IGNORECASE):
            statements.append(stmt)

    return statements


def main():
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
            finally:
                pass
        cur.close()
        total += ok
        print(f"   {ok} ok, {skip} skip, {fail} errores")

    conn.close()
    print(f"\nCompleto. {total} sentencias ejecutadas.")


if __name__ == "__main__":
    main()
