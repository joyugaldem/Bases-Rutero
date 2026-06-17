# Lácteos María del Carmen — Sistema de Facturación

Sistema de facturación para Productos Lácteos María del Carmen.
Módulo de facturación con clientes, rutas, productos y reportes.

## Stack
- Flask 3.0 + Python 3.12
- MySQL 8.0 (Railway managed)
- Stored procedures + triggers para lógica de negocio
- Bootstrap 5 vía CDN
- Jinja2 templates

## Setup Local

### 1. Clonar repo
```bash
git clone https://github.com/joyugaldem/Bases-Rutero.git
cd Bases-Rutero
```

### 2. Crear entorno virtual
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 3. Configurar entorno
```bash
cp .env.example .env
# Editar .env con los valores locales
```

### 4. Levantar MySQL con Docker
```bash
docker run -d \
  -e MYSQL_ROOT_PASSWORD=test \
  -e MYSQL_DATABASE=lacteosdb \
  -p 3306:3306 \
  mysql:8.0
```

### 5. Inicializar base de datos
```bash
python scripts/bootstrap_db.py
```

Deberías ver:
```
→ 01_schema.sql
   36 ok, 0 skip, 0 errores
→ 02_crud.sql
   248 ok, 0 skip, 0 errores
Bootstrap completo. 248 sentencias ejecutadas.
```

### 6. Correr la app
```bash
python app.py
# o con gunicorn:
gunicorn wsgi:app
```

Abrir http://localhost:5000

## Deploy a Railway

Ver [RAILWAY_SETUP_CLI.md](../RAILWAY_SETUP_CLI.md) para instrucciones paso a paso.

## Variables de Entorno

| Variable | Descripción | Default |
|---|---|---|
| `DB_HOST` | Host MySQL | `localhost` |
| `DB_PORT` | Puerto MySQL | `3306` |
| `DB_NAME` | Nombre base de datos | `lacteosdb` |
| `DB_USER` | Usuario MySQL | `root` |
| `DB_PASSWORD` | Password MySQL | `""` |
| `SECRET_KEY` | Clave secreta Flask | (requerido en prod) |
| `FLASK_DEBUG` | Modo debug | `1` |
| `PORT` | Puerto HTTP | `5000` |
| `APPLY_DB_*` | Vars para apply_procs.py | ( Railway ) |

## Módulos

- **Productos**: Crear, editar, eliminar productos y presentaciones
- **Clientes**: Gestión de clientes con crédito autorizado y rutas
- **Rutas/Repartidores**: Administración de rutas y asignaciones
- **Facturación**: Facturas de contado y crédito, registro de pagos
- **Reportes**: Ventas por ruta, créditos pendientes, productos por vencer

## Tests

```bash
pip install pytest pytest-mysql
pytest tests/
```

Con Docker CI:
```bash
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

## Arquitectura

Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para diagramas de flujo y estructura de datos.

## Requisitos Funcionales

Ver [docs/RF.md](docs/RF.md) para el inventario completo de RF con traceability.

## Troubleshooting

### "SECRET_KEY no puede ser el valor por defecto"
```bash
export SECRET_KEY=$(openssl rand -hex 32)
```

### "No hay stock disponible"
Verificar que existen lotes con `cantidad_disponible > 0` para la presentación.

### "El cliente no tiene crédito autorizado"
Editar el cliente y marcar "Crédito autorizado" = true.

### "Factura tiene pagos registrados"
Los pagos son históricos. Para "anular" la deuda, registrar un pago negativo o usar nota de crédito (próxima versión).
