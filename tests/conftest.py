"""Pytest fixtures para tests de integración con MySQL."""
import os
import sys
import pytest


# Configurar SECRET_KEY ANTES de importar app/config, porque config.py
# ahora exige la variable y lanza RuntimeError si falta. Usamos una key
# fija de dev (>= 32 chars para no romper el check de prod).
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-32-chars")
os.environ.setdefault("FLASK_DEBUG", "1")

# Mapear TEST_DB_* a DB_* para que config.py (que lee DB_*) use los
# mismos valores que las fixtures. Sin esto, config intenta conectar
# a localhost:3306 mientras las fixtures usan TEST_DB_HOST:TEST_DB_PORT.
for var_in, var_out in (
    ("TEST_DB_HOST", "DB_HOST"),
    ("TEST_DB_PORT", "DB_PORT"),
    ("TEST_DB_USER", "DB_USER"),
    ("TEST_DB_PASSWORD", "DB_PASSWORD"),
    ("TEST_DB_NAME", "DB_NAME"),
):
    val = os.environ.get(var_in)
    if val is not None:
        os.environ.setdefault(var_out, val)

# Añade el directorio raíz al path para poder importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _try_connect():
    """Intenta abrir una conexión MySQL con las variables TEST_DB_*.

    Es silenciosa: si MySQL no está disponible (entorno local sin
    Docker, CI en otra red), devuelve None en lugar de lanzar
    excepción. El caller decide si skippear o fallar.

    Returns:
        mysql.connector.connection.MySQLConnection | None.
    """
    import mysql.connector
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("TEST_DB_HOST", "localhost"),
            port=int(os.environ.get("TEST_DB_PORT", "3306")),
            user=os.environ.get("TEST_DB_USER", "root"),
            password=os.environ.get("TEST_DB_PASSWORD", "test"),
            database=os.environ.get("TEST_DB_NAME", "lacteosdb"),
            charset="utf8mb4",
            autocommit=True,
            connection_timeout=5,
        )
        return conn
    except Exception:
        return None


@pytest.fixture(scope="session")
def mysql_connection():
    """Conexión MySQL compartida por toda la sesión de pytest.

    Si MySQL no responde en `TEST_DB_HOST:TEST_DB_PORT`, hace
    `pytest.skip` para que los tests dependientes se marquen como
    omitidos en lugar de fallar. El bootstrap del schema lo hace el CI
    (o manualmente con `python scripts/bootstrap_db.py`) antes de
    correr pytest; este fixture solo abre la conexión.

    Yields:
        mysql.connector.connection.MySQLConnection: misma instancia
        para todos los tests de la sesión (más rápido que reconectar).
    """
    conn = _try_connect()
    if conn is None:
        pytest.skip(
            "MySQL no disponible en TEST_DB_HOST:TEST_DB_PORT. "
            "Levanta MySQL o ajusta las variables TEST_DB_*"
        )
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def clean_db(mysql_connection):
    """Vacía las tablas antes y después de cada test de integración.

    El orden es importante: las tablas hijas (factura, detalle, lote)
    se borran ANTES que las padres (persona, producto) para no violar
    las FK constraints. Se listan explícitamente en lugar de hacer
    `SHOW TABLES` para tener control sobre dependencias.

    Yields:
        None: cede el control al test. La limpieza post-test garantiza
        que el siguiente test no herede filas residuales.
    """
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
