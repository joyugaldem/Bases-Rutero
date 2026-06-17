-- ============================================================
-- Vistas (3)
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;

-- ============================================================
-- VISTA 1: vista_facturas_pendientes
-- Muestra todas las facturas a crédito con saldo mayor a cero,
-- incluyendo datos del cliente, repartidor, ruta y el detalle
-- de lo adeudado. Útil para la gestión de cobranza (HU-17, HU-18).
-- ============================================================
CREATE OR REPLACE VIEW vista_facturas_pendientes AS
SELECT
    f.id_factura,
    f.numero_factura,
    c.razon_social                         AS cliente,
    p_cli.nombre                           AS nombre_contacto,
    f.total                                AS monto_total,
    fcc.saldo_pendiente,
    f.total - fcc.saldo_pendiente          AS total_pagado,
    fcc.fecha_vencimiento_credito,
    DATEDIFF(fcc.fecha_vencimiento_credito, CURRENT_DATE) AS dias_para_vencer,
    f.fecha_emision,
    ru.nombre                              AS ruta,
    p_rep.nombre                           AS repartidor
FROM factura f
JOIN factura_credito fcc ON fcc.id_factura = f.id_factura
JOIN cliente c           ON c.id_cliente   = f.id_cliente
JOIN persona p_cli       ON p_cli.id_persona = c.id_persona
JOIN repartidor rep      ON rep.id_repartidor = f.id_repartidor
JOIN persona p_rep       ON p_rep.id_persona  = rep.id_persona
JOIN recorrido_ruta rr   ON rr.id_recorrido  = f.id_recorrido
JOIN ruta ru             ON ru.id_ruta       = rr.id_ruta
WHERE fcc.saldo_pendiente > 0
  AND f.estado_factura = 'Pendiente';

-- ============================================================
-- VISTA 2: vista_catalogo_productos
-- Catálogo completo de productos activos con sus presentaciones
-- vigentes, precio de venta y stock disponible por lote.
-- Útil para el módulo de facturación y para reportes (HU-04).
-- ============================================================
CREATE OR REPLACE VIEW vista_catalogo_productos AS
SELECT
    pd.id_producto,
    pd.nombre_comercial,
    pd.codigo_barras,
    pd.categoria,
    pr.id_presentacion,
    CONCAT(pr.tamano, ' ', pr.unidad_medida) AS presentacion,
    pr.precio_venta,
    l.id_lote,
    l.numero_lote,
    l.fecha_vencimiento,
    l.cantidad_disponible,
    l.estado_lote,
    DATEDIFF(l.fecha_vencimiento, CURRENT_DATE) AS dias_para_vencer
FROM producto pd
JOIN presentacion pr ON pr.id_producto = pd.id_producto
JOIN lote l          ON l.id_producto  = pd.id_producto
WHERE pd.estado_producto     = 'Activo'
  AND pr.estado_presentacion = 'Activa'
  AND l.estado_lote          = 'Disponible'
ORDER BY pd.nombre_comercial, pr.tamano, l.fecha_vencimiento;

-- ============================================================
-- VISTA 3: vista_ventas_por_ruta
-- Resumen de ventas agrupadas por ruta y mes, con conteo de
-- facturas, clientes atendidos y monto total generado.
-- Implementa el reporte RF-18 / HU-19.
-- ============================================================
CREATE OR REPLACE VIEW vista_ventas_por_ruta AS
SELECT
    ru.id_ruta,
    ru.nombre                               AS ruta,
    ru.zona_geografica,
    YEAR(f.fecha_emision)                   AS anio,
    MONTH(f.fecha_emision)                  AS mes,
    COUNT(DISTINCT f.id_factura)            AS total_facturas,
    COUNT(DISTINCT f.id_cliente)            AS clientes_atendidos,
    SUM(f.total)                            AS monto_total,
    SUM(IF(f.condicion_pago = 'Contado', f.total, 0)) AS ventas_contado,
    SUM(IF(f.condicion_pago = 'Crédito', f.total, 0)) AS ventas_credito
FROM factura f
JOIN recorrido_ruta rr ON rr.id_recorrido = f.id_recorrido
JOIN ruta ru           ON ru.id_ruta      = rr.id_ruta
WHERE f.estado_factura != 'Anulada'
GROUP BY ru.id_ruta, ru.nombre, ru.zona_geografica,
         YEAR(f.fecha_emision), MONTH(f.fecha_emision)
ORDER BY ru.nombre, anio DESC, mes DESC;
