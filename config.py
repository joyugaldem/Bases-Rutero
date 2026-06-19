"""
Configuración de la aplicación Flask y conexión a MySQL.
Lee de variables de entorno; cae a valores por defecto para dev local.

SECRET_KEY es obligatorio en todos los entornos. No hay valor por
defecto hardcodeado: en dev se debe setear explícitamente (e.g. en .env).
"""

import os

DB_HOST     = os.environ.get("DB_HOST", "localhost")
DB_PORT     = int(os.environ.get("DB_PORT", 3306))
DB_NAME     = os.environ.get("DB_NAME", "lacteosdb")
DB_USER     = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# SECRET_KEY: obligatorio. En dev se puede usar uno fijo, pero debe ser
# explícito (no hay default). En producción se exige uno de >= 32 chars.
_secret_env = os.environ.get("SECRET_KEY", "")
if not _secret_env:
    raise RuntimeError(
        "SECRET_KEY es obligatorio. Define la variable de entorno "
        "SECRET_KEY con un valor seguro, e.g. "
        "`export SECRET_KEY=$(openssl rand -hex 32)`"
    )
SECRET_KEY = _secret_env

FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

if not FLASK_DEBUG and len(SECRET_KEY) < 32:
    raise RuntimeError(
        f"SECRET_KEY debe tener al menos 32 caracteres en producción "
        f"(actual: {len(SECRET_KEY)}). Genera uno con: "
        f"openssl rand -hex 32"
    )
