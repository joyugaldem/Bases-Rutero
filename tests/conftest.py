"""Pytest fixtures para tests de integración con MySQL."""
import os
import sys
import subprocess
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def mysql_connection():
    """Conexión a MySQL de test (Docker service)."""
    import mysql.connector

    conn = mysql.connector.connect(
        host=os.environ.get("TEST_DB_HOST", "localhost"),
        port=int(os.environ.get("TEST_DB_PORT", "3306")),
        user=os.environ.get("TEST_DB_USER", "root"),
        password=os.environ.get("TEST_DB_PASSWORD", "test"),
        database=os.environ.get("TEST_DB_NAME", "lacteosdb_test"),
        charset="utf8mb4",
        autocommit=True,
    )
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def db_cursor(mysql_connection):
    """Cursor reutilizable para la sesión."""
    cur = mysql_connection.cursor()
    yield cur
    cur.close()


@pytest.fixture(scope="function")
def clean_db(mysql_connection):
    """Limpia tablas en orden inverso al de inserción antes de cada test."""
    tables_in_order = [
        "venta",
        "pago",
        "factura_credito",
        "factura_contado",
        "detalle_factura",
        "factura",
        "lote",
        "presentacion",
        "asignacion_ruta",
        "recorrido_ruta",
        "telefono_persona",
        "cliente",
        "repartidor",
        "ruta",
        "persona",
        "producto",
    ]
    cur = mysql_connection.cursor()
    for table in tables_in_order:
        try:
            cur.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    mysql_connection.commit()
    cur.close()
    yield
    for table in tables_in_order:
        try:
            cur.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    mysql_connection.commit()


@pytest.fixture(scope="session")
def bootstrap_db():
    """Bootstrap de la BD de test (solo una vez por sesión)."""
    test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(test_dir, "scripts", "bootstrap_db.py")

    result = subprocess.run(
        [sys.executable, script_path],
        env={**os.environ, "DB_NAME": "lacteosdb_test"},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"bootstrap_db.py falló:\n{result.stderr}")
    yield
