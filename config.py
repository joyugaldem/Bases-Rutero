"""
Configuración de la aplicación Flask y conexión a MySQL.
Ajustar DB_USER y DB_PASSWORD según el entorno local.
"""

DB_HOST     = "localhost"
DB_PORT     = 3306
DB_NAME     = "lacteosdb"
DB_USER     = "root"         # Cambiar según configuración local
DB_PASSWORD = ""             # Cambiar según configuración local

SECRET_KEY  = "lacteos_tec_2026_secreto"
