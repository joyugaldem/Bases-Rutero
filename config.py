"""
Configuración de la aplicación Flask y conexión a MySQL.
Lee de variables de entorno; cae a valores por defecto para dev local.
"""

import os

DB_HOST     = os.environ.get("DB_HOST", "localhost")
DB_PORT     = int(os.environ.get("DB_PORT", 3306))
DB_NAME     = os.environ.get("DB_NAME", "lacteosdb")
DB_USER     = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

SECRET_KEY  = os.environ.get("SECRET_KEY", "lacteos_tec_2026_secreto")
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

if not FLASK_DEBUG and SECRET_KEY == "lacteos_tec_2026_secreto":
    raise RuntimeError("SECRET_KEY no puede ser el valor por defecto en producción")
