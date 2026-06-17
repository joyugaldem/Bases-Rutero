import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def _ensure_stored_procs():
    try:
        from scripts.recreate_stored_procs import run as recreate_sps
        print("[wsgi] Ensuring stored procedures exist in DB...")
        recreate_sps()
        print("[wsgi] Stored procedures ready.")
    except Exception as e:
        print(f"[wsgi] Warning: could not ensure stored procedures: {e}")

_ensure_stored_procs()

from app import app

if __name__ == "__main__":
    app.run()
