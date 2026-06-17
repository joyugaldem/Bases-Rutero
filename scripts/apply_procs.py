"""Apply all SQL files to Railway MySQL via public proxy."""
import re, glob, os
import mysql.connector

HOST = "thomas.proxy.rlwy.net"
PORT = 51505
USER = "root"
PASSWORD = "fMYzIpahogVvRVHCACmBTOBQMzAEZevy"
DB = "railway"


def split_sql(content):
    """Split SQL content into executable statements, handling DELIMITER changes."""
    delimiter = ";"
    statements = []
    current_lines = []

    for line in content.splitlines():
        stripped = line.strip()

        # Handle DELIMITER directive
        m = re.match(r"^DELIMITER\s+(\S+)\s*$", stripped, re.IGNORECASE)
        if m:
            delimiter = m.group(1)
            continue

        # Skip pure comment lines and empty lines while buffer is empty
        if not stripped or stripped.startswith("--"):
            if current_lines:
                current_lines.append(line)
            continue

        current_lines.append(line)

        # Check if this line ends with the current delimiter
        if stripped.endswith(delimiter):
            stmt = "\n".join(current_lines)
            # Remove trailing delimiter
            stmt = stmt.rstrip()
            if stmt.endswith(delimiter):
                stmt = stmt[: -len(delimiter)].rstrip()

            # Strip comments and check it's not a USE statement
            clean = re.sub(r"--.*$", "", stmt, flags=re.MULTILINE).strip()
            clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL).strip()

            if clean and not re.match(r"^USE\b", clean, re.IGNORECASE):
                statements.append(stmt)

            current_lines = []

    # Flush anything remaining
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
        ok = fail = 0
        for s in stmts:
            if not s.strip():
                continue
            cur = conn.cursor()
            try:
                cur.execute(s)
                # consume any leftover result sets (from triggers, etc.)
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
                    ok += 1  # idempotent
                else:
                    fail += 1
                    print(f"   [!] {s[:80].strip()}... -> {err[:120]}")
            finally:
                cur.close()
        total += ok
        print(f"   {ok} ok, {fail} errores")

    conn.close()
    print(f"\nCompleto. {total} sentencias ejecutadas.")


if __name__ == "__main__":
    main()
