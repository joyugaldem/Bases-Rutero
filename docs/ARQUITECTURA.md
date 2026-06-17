# Sistema de Facturación — Lácteos María del Carmen

## Stack Tecnológico
- **Backend**: Flask 3.0 + Python 3.12
- **Base de datos**: MySQL 8.0 (Railway managed)
- **Lógica de negocio**: Stored procedures + triggers (MySQL)
- **Frontend**: Bootstrap 5 vía CDN, Jinja2 templates
- **Deploy**: Railway (Python Nixpacks)

## Estructura del Proyecto

```
Bases-Rutero/
├── app.py                  # Aplicación Flask (30+ rutas)
├── config.py                # Configuración de entorno
├── db.py                    # Helpers de acceso a MySQL
├── constants.py             # Listas centralizadas
├── wsgi.py                  # Hook de inicio (gunicorn)
├── requirements.txt         # Dependencias Python
├── Procfile                # Deploy hook
├── .env.example            # Variables de entorno de ejemplo
├── sql/
│   ├── 01_schema.sql        # CREATE DATABASE, tablas, índices
│   ├── 02_crud.sql         # SPs CRUD (insertar, modificar, consultar, eliminar)
│   ├── 03_transacciones.sql # SPs transaccionales + triggers
│   ├── 04_consultas.sql    # Vistas materializadas (reportes)
│   └── 05_datos.sql        # Datos de prueba
├── scripts/
│   ├── bootstrap_db.py      # Inicializa toda la BD (248 stmts)
│   └── recreate_stored_procs.py  # Recrea SPs y triggers
├── templates/               # Jinja2 templates por módulo
│   ├── index.html
│   ├── productos/
│   ├── clientes/
│   ├── rutas/
│   ├── facturacion/
│   └── reportes/
└── tests/                  # Suite pytest
```

## Arquitectura de la Base de Datos

### Entidades Principales

```
persona (E-01) ─────┬──► cliente (E-03)
                    ├──► repartidor (E-04)

telefono_persona (E-02) ──► persona

ruta (E-05) ───► asignacion_ruta (E-06) ──► repartidor
         └──► recorrido_ruta (E-07) ──► asignacion_ruta

producto (E-08) ──► presentacion (E-09) ──► lote (E-10)

factura (E-11)
  ├── detalle_factura (E-12) ──► presentacion, lote
  ├── factura_contado (E-13)    [si condición=Contado]
  └── factura_credito (E-14)   [si condición=Crédito]
                                 └──► pago (E-15)
                                        └──► venta (E-16) ──► detalle_factura
```

## Flujos de Negocio

### Crear Factura (Contado)
```
1. app.py:factura_nueva() POST
2. sp_trx_crear_factura_completa()
   ├── Valida stock del lote (FOR UPDATE)
   ├── Genera número FAC-00001
   ├── INSERT factura + detalle_factura
   ├── UPDATE lote (resta stock)
   ├── INSERT factura_contado (marca Pagada)
   └── INSERT venta
3. Redirige a /facturacion/<id>
```

### Crear Factura (Crédito)
```
1. app.py:factura_nueva() POST
2. sp_trx_crear_factura_completa()
   ├── Valida cliente tiene credito_autorizado=TRUE
   ├── Genera número FAC-00001
   ├── INSERT factura + detalle_factura
   ├── UPDATE lote (resta stock)
   ├── INSERT factura_credito (saldo = total, estado=Pendiente)
   ├── UPDATE factura (estado=Pendiente)
   └── INSERT venta
3. Redirige a /facturacion/<id>
```

### Registrar Pago (Crédito)
```
1. app.py:factura_pagar() POST
2. sp_trx_registrar_pago()
   ├── SELECT saldo_pendiente FOR UPDATE (bloquea)
   ├── Valida monto <= saldo
   ├── INSERT pago
   └── trg_pago_after_insert (trigger):
       ├── UPDATE factura_credito SET saldo -= monto
       └── IF saldo = 0 THEN UPDATE factura SET estado=Pagada
3. Lee saldo actualizado (trigger lo manejó)
```

### Anular Factura
```
1. app.py:factura_anular() POST
2. sp_trx_anular_factura()
   ├── Valida estado IN ('Emitida', 'Pendiente')
   ├── Bloquea si es Crédito con pagos existentes
   ├── Cursor: UPDATE lote SET cantidad_disponible += cantidad
   ├── DELETE factura_credito (si aplica)
   └── UPDATE factura SET estado='Anulada'
```

## Stored Procedures Principales

| SP | Archivo | Descripción |
|---|---|---|
| `sp_trx_crear_factura_completa` | 03_transacciones.sql | Crea factura atómica |
| `sp_trx_registrar_pago` | 03_transacciones.sql | Registra pago + actualiza saldo |
| `sp_trx_anular_factura` | 03_transacciones.sql | Anula + restaura stock |
| `sp_trx_crear_recorrido` | 03_transacciones.sql | Crea recorrido con validación |
| `sp_insertar_cliente` | 02_crud.sql | Inserta persona+cliente en tx |
| `sp_consultar_factura` | 03_transacciones.sql | Consulta factura por ID |

## Triggers

| Trigger | Tabla | Evento | Efecto |
|---|---|---|---|
| `trg_pago_after_insert` | pago | INSERT | Actualiza saldo y estado de factura_credito |
