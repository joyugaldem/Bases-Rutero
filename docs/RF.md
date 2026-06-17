# Requisitos Funcionales — Lácteos María del Carmen

## RF-01 — Gestión de Productos
- [x] Crear producto con nombre, código de barras, categoría
- [x] Modificar producto existente
- [x] Eliminar producto (lógico si tiene ventas)
- [x] Consultar producto individual y lista completa
- [x] Estados: Activo, Inactivo, Descontinuado

**SP**: `sp_insertar_producto`, `sp_modificar_producto`, `sp_eliminar_producto`, `sp_consultar_productos`

## RF-02 — Gestión de Presentaciones
- [x] Agregar presentaciones a un producto (tamaño, unidad, precio)
- [x] Consultar presentaciones por producto
- [x] Estados: Activa, Inactiva

**SP**: `sp_insertar_presentacion`, `sp_consultar_presentaciones`

## RF-03 — Gestión de Lotes
- [x] Registrar lote con fechas de elaboración/vencimiento
- [x] Control de stock disponible por lote
- [x] Estado automático: Agotado cuando stock = 0
- [x] Restaurar stock al anular factura

**SP**: `sp_insertar_lote`, `sp_consultar_lotes`

## RF-04 — Gestión de Clientes
- [x] Crear cliente con datos de persona + razón social + dirección
- [x] Autorizar/revocar crédito
- [x] Asignar a ruta de distribución
- [x] Estados: Activo, Inactivo, Suspendido
- [x] Registrar teléfonos

**SP**: `sp_insertar_cliente` (tx), `sp_modificar_cliente`, `sp_eliminar_cliente`, `sp_consultar_clientes`

## RF-05 — Gestión de Rutas
- [x] Crear ruta con nombre y zona geográfica
- [x] Estados: Activa, Inactiva, Suspendida
- [x] Asignar repartidor a ruta
- [x] Crear recorridos (fecha + turno)

**SP**: `sp_insertar_ruta`, `sp_modificar_ruta`, `sp_consultar_rutas`, `sp_consultar_asignaciones`

## RF-06 — Gestión de Repartidores
- [x] Crear repartidor con nombre y licencia
- [x] Estados: Activo, Inactivo, Suspendido
- [x] Validar repartidor activo al crear recorrido

**SP**: `sp_insertar_repartidor`, `sp_modificar_repartidor`, `sp_consultar_repartidores`

## RF-07 — Gestión de Recorridos
- [x] Crear recorrido verificando repartidor y ruta activos
- [x] Turnos: Mañana, Tarde, Noche
- [x] Crear asignación si no existe

**SP**: `sp_trx_crear_recorrido` (tx)

## RF-08 — Facturación Contado
- [x] Crear factura con detalle
- [x] Validar stock disponible (FOR UPDATE)
- [x] Calcular vuelto automáticamente
- [x] Generar número secuencial FAC-00001
- [x] Marcar Pagada al instante
- [x] Registrar en venta para reportes

**SP**: `sp_trx_crear_factura_completa` (tx)

## RF-09 — Facturación Crédito
- [x] Crear factura a crédito
- [x] Validar cliente tiene crédito autorizado
- [x] Registrar fecha de vencimiento y límite
- [x] Saldo pendiente = total inicial
- [x] Estado: Pendiente

**SP**: `sp_trx_crear_factura_completa` (tx), `sp_consultar_factura_credito`

## RF-10 — Registro de Pagos
- [x] Registrar pago parcial o total
- [x] Validar monto <= saldo pendiente
- [x] Bloquear registro si no existe factura_credito
- [x] Trigger actualiza saldo y estado automáticamente
- [x] Marcar Pagada cuando saldo = 0
- [x] Soporte: Efectivo, Transferencia, SINPE, Cheque

**SP**: `sp_trx_registrar_pago` (tx)
**Trigger**: `trg_pago_after_insert`

## RF-11 — Anulación de Facturas
- [x] Anular solo estado 'Emitida' o 'Pendiente'
- [x] Restaurar stock de lotes
- [x] Bloquear anulación si hay pagos (CRÉDITO)
- [x] Eliminar registro de crédito (sin tocar pagos históricos)
- [x] Marcar estado 'Anulada'

**SP**: `sp_trx_anular_factura` (tx)

## RF-12 — Consulta de Facturas
- [x] Listar todas con filtros por cliente y rango de fechas
- [x] Detalle individual con productos, pagos y crédito
- [x] Evitar carga de TODAS las facturas para ver una (SP dedicado)

**SP**: `sp_consultar_facturas`, `sp_consultar_factura`

## RF-13 — Reporte de Créditos
- [x] Resumen de todas las facturas a crédito pendientes
- [x] Mostrar saldo pendiente y fecha de vencimiento

**SP**: `sp_cur_resumen_creditos`

## RF-14 — Reporte de Ventas por Ruta
- [x] Total de ventas por ruta en rango de fechas
- [x] Incluye nombre de ruta y fecha

**SP**: `sp_rpt_ventas_por_ruta`

## RF-15 — Reporte de Productos Próximos a Vencer
- [x] Lotes que vencen en los próximos N días
- [x] Incluir stock disponible

**SP**: `sp_rpt_productos_proximos_vencer`

## RF-16 — Reporte Top Productos
- [x] Productos más vendidos en rango de fechas
- [x] Cantidad y monto total

**SP**: `sp_rpt_top_productos_vendidos`

## RF-17 — Módulo Telefónico
- [x] Registrar teléfonos por persona
- [x] Tipos: Móvil, Casa, Trabajo, Otro
- [x] Modificar y eliminar teléfonos

**SP**: `sp_insertar_telefono`, `sp_modificar_telefono`, `sp_eliminar_telefono`

## RF-18 — Integridad Transaccional
- [x] Todas las operaciones multi-tabla usan START TRANSACTION + COMMIT
- [x] ROLLBACK automático en excepciones (EXIT HANDLER)
- [x] No dejar registros huérfanos (persona sin cliente)
- [x] Bloqueo FOR UPDATE en pagos para evitar race conditions

**Notas**: Implementado en todos los SPs tx.*

## Notas de Traceability

| Archivo | SPs |
|---|---|
| `sql/01_schema.sql` | Tablas, índices, FK, triggers |
| `sql/02_crud.sql` | sp_insertar_cliente (tx), CRUD para todas las entidades |
| `sql/03_transacciones.sql` | sp_trx_crear_factura_completa, sp_trx_registrar_pago, sp_trx_anular_factura, sp_trx_crear_recorrido |
| `sql/04_consultas.sql` | Vistas para reportes |
| `sql/05_datos.sql` | Datos de prueba |
