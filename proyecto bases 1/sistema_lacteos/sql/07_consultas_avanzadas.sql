-- ============================================================
-- Consultas Avanzadas (5) implementadas como procedimientos
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- Cada consulta accede a múltiples tablas, usa agregaciones,
-- subconsultas o CTEs para cumplir un alto nivel de complejidad.
-- ============================================================
USE lacteosdb;
DELIMITER //

-- ============================================================
-- CONSULTA 1: sp_rpt_ventas_por_ruta
-- RF-18 / HU-19: Reporte de ventas totales por ruta de
-- distribución en un rango de fechas. Incluye conteo de
-- facturas, clientes únicos, monto total y desglose por
-- condición de pago. Ordena por monto total descendente.
-- Tablas: factura, recorrido_ruta, ruta, cliente.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_rpt_ventas_por_ruta //
CREATE PROCEDURE sp_rpt_ventas_por_ruta(
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT
        ru.nombre                             AS ruta,
        ru.zona_geografica,
        COUNT(DISTINCT f.id_factura)          AS total_facturas,
        COUNT(DISTINCT f.id_cliente)          AS clientes_unicos,
        SUM(f.total)                          AS monto_total,
        SUM(IF(f.condicion_pago='Contado', f.total, 0)) AS total_contado,
        SUM(IF(f.condicion_pago='Crédito', f.total, 0)) AS total_credito,
        AVG(f.total)                          AS promedio_factura,
        MAX(f.total)                          AS factura_mayor,
        MIN(f.total)                          AS factura_menor
    FROM factura f
    JOIN recorrido_ruta rr ON rr.id_recorrido = f.id_recorrido
    JOIN ruta ru           ON ru.id_ruta      = rr.id_ruta
    WHERE f.estado_factura != 'Anulada'
      AND (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta)
    GROUP BY ru.id_ruta, ru.nombre, ru.zona_geografica
    ORDER BY monto_total DESC;
END //

-- ============================================================
-- CONSULTA 2: sp_rpt_historial_cliente
-- RF-19 / HU-20: Historial de ventas detallado por cliente.
-- Muestra cada factura con sus ítems, monto total y el saldo
-- pendiente en caso de ser a crédito. Usa subconsulta para
-- calcular cuánto ha pagado cada cliente en total.
-- Tablas: cliente, persona, factura, detalle_factura,
--         presentacion, producto, factura_credito, pago.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_rpt_historial_cliente //
CREATE PROCEDURE sp_rpt_historial_cliente(
    IN p_id_cliente INT
)
BEGIN
    -- Resumen general del cliente
    SELECT
        c.id_cliente,
        p.nombre                               AS nombre_contacto,
        c.razon_social,
        c.credito_autorizado,
        ru.nombre                              AS ruta_asignada,
        COUNT(DISTINCT f.id_factura)           AS total_facturas,
        SUM(f.total)                           AS total_comprado,
        SUM(IF(f.condicion_pago='Contado', f.total, 0)) AS compras_contado,
        SUM(IF(f.condicion_pago='Crédito', f.total, 0)) AS compras_credito,
        COALESCE((
            SELECT SUM(pg.monto)
            FROM pago pg
            JOIN factura_credito fcc2 ON fcc2.id_factura = pg.id_factura_credito
            JOIN factura f2 ON f2.id_factura = fcc2.id_factura
            WHERE f2.id_cliente = c.id_cliente
        ), 0)                                  AS total_pagado,
        COALESCE(SUM(fcc.saldo_pendiente), 0)  AS saldo_total_pendiente
    FROM cliente c
    JOIN persona p       ON p.id_persona  = c.id_persona
    LEFT JOIN ruta ru    ON ru.id_ruta    = c.id_ruta
    LEFT JOIN factura f  ON f.id_cliente  = c.id_cliente AND f.estado_factura != 'Anulada'
    LEFT JOIN factura_credito fcc ON fcc.id_factura = f.id_factura
    WHERE c.id_cliente = p_id_cliente
    GROUP BY c.id_cliente, p.nombre, c.razon_social,
             c.credito_autorizado, ru.nombre;

    -- Detalle de facturas
    SELECT
        f.numero_factura,
        f.fecha_emision,
        f.condicion_pago,
        f.estado_factura,
        f.total,
        COALESCE(fcc.saldo_pendiente, 0)       AS saldo_pendiente,
        COALESCE(fcc.fecha_vencimiento_credito, NULL) AS vence_credito,
        COUNT(df.id_detalle)                   AS items
    FROM factura f
    LEFT JOIN factura_credito fcc ON fcc.id_factura = f.id_factura
    LEFT JOIN detalle_factura df  ON df.id_factura  = f.id_factura
    WHERE f.id_cliente = p_id_cliente
      AND f.estado_factura != 'Anulada'
    GROUP BY f.id_factura, f.numero_factura, f.fecha_emision,
             f.condicion_pago, f.estado_factura, f.total,
             fcc.saldo_pendiente, fcc.fecha_vencimiento_credito
    ORDER BY f.fecha_emision DESC;
END //

-- ============================================================
-- CONSULTA 3: sp_rpt_productos_proximos_vencer
-- RF-04: Identifica presentaciones de productos con lotes
-- que vencen en los próximos N días y aún tienen stock.
-- Útil para planificación de distribución prioritaria.
-- Tablas: lote, producto, presentacion.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_rpt_productos_proximos_vencer //
CREATE PROCEDURE sp_rpt_productos_proximos_vencer(
    IN p_dias INT   -- Cantidad de días hacia adelante a revisar
)
BEGIN
    SELECT
        pd.nombre_comercial,
        pd.categoria,
        CONCAT(pr.tamano,' ',pr.unidad_medida) AS presentacion,
        pr.precio_venta,
        l.numero_lote,
        l.fecha_elaboracion,
        l.fecha_vencimiento,
        DATEDIFF(l.fecha_vencimiento, CURRENT_DATE) AS dias_para_vencer,
        l.cantidad_disponible,
        l.cantidad_disponible * pr.precio_venta     AS valor_en_riesgo
    FROM lote l
    JOIN producto pd    ON pd.id_producto    = l.id_producto
    JOIN presentacion pr ON pr.id_producto   = pd.id_producto
    WHERE l.estado_lote  = 'Disponible'
      AND pd.estado_producto = 'Activo'
      AND pr.estado_presentacion = 'Activa'
      AND l.fecha_vencimiento BETWEEN CURRENT_DATE
                                  AND DATE_ADD(CURRENT_DATE, INTERVAL COALESCE(p_dias,30) DAY)
    ORDER BY l.fecha_vencimiento ASC, valor_en_riesgo DESC;
END //

-- ============================================================
-- CONSULTA 4: sp_rpt_top_productos_vendidos
-- RF-20 / HU-21: Ranking de presentaciones de productos por
-- volumen de unidades vendidas e ingresos generados en un
-- período. Excluye facturas anuladas y usa subconsulta para
-- calcular el porcentaje del total de ventas.
-- Tablas: detalle_factura, factura, presentacion, producto.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_rpt_top_productos_vendidos //
CREATE PROCEDURE sp_rpt_top_productos_vendidos(
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE,
    IN p_top         INT    -- Limitar resultados, NULL = todos
)
BEGIN
    DECLARE v_total_global DECIMAL(14,2);
    DECLARE v_limit        BIGINT UNSIGNED DEFAULT 18446744073709551615;

    IF p_top IS NOT NULL THEN SET v_limit = p_top; END IF;

    -- Total global del período para calcular porcentajes
    SELECT COALESCE(SUM(f.total),0) INTO v_total_global
    FROM factura f
    WHERE f.estado_factura != 'Anulada'
      AND (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta);

    SELECT
        pd.nombre_comercial,
        pd.categoria,
        CONCAT(pr.tamano,' ',pr.unidad_medida)  AS presentacion,
        pr.precio_venta                          AS precio_actual,
        SUM(df.cantidad)                         AS unidades_vendidas,
        SUM(df.subtotal)                         AS ingresos_generados,
        ROUND(SUM(df.subtotal) / NULLIF(v_total_global,0) * 100, 2) AS pct_del_total,
        COUNT(DISTINCT f.id_factura)             AS en_cuantas_facturas,
        COUNT(DISTINCT f.id_cliente)             AS clientes_distintos
    FROM detalle_factura df
    JOIN factura f       ON f.id_factura       = df.id_factura
    JOIN presentacion pr ON pr.id_presentacion = df.id_presentacion
    JOIN producto pd     ON pd.id_producto     = pr.id_producto
    WHERE f.estado_factura != 'Anulada'
      AND (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta)
    GROUP BY pd.id_producto, pd.nombre_comercial, pd.categoria,
             pr.id_presentacion, pr.tamano, pr.unidad_medida, pr.precio_venta
    ORDER BY ingresos_generados DESC
    LIMIT v_limit;
END //

-- ============================================================
-- CONSULTA 5: sp_rpt_analisis_repartidor
-- Análisis de rendimiento por repartidor: total vendido,
-- clientes atendidos, rutas cubiertas y promedio por factura
-- en un período dado. Usa subconsulta correlacionada para
-- calcular la factura máxima emitida por cada repartidor.
-- Tablas: repartidor, persona, factura, recorrido_ruta, ruta, cliente.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_rpt_analisis_repartidor //
CREATE PROCEDURE sp_rpt_analisis_repartidor(
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT
        rep.id_repartidor,
        p.nombre                                AS repartidor,
        rep.licencia,
        rep.estado_repartidor,
        GROUP_CONCAT(DISTINCT ru.nombre ORDER BY ru.nombre SEPARATOR ', ') AS rutas_cubiertas,
        COUNT(DISTINCT f.id_factura)            AS facturas_emitidas,
        COUNT(DISTINCT f.id_cliente)            AS clientes_atendidos,
        SUM(f.total)                            AS monto_total_vendido,
        AVG(f.total)                            AS promedio_por_factura,
        MAX(f.total)                            AS factura_mas_alta,
        (
            SELECT f2.numero_factura
            FROM factura f2
            WHERE f2.id_repartidor = rep.id_repartidor
              AND f2.estado_factura != 'Anulada'
              AND (p_fecha_desde IS NULL OR f2.fecha_emision >= p_fecha_desde)
              AND (p_fecha_hasta IS NULL OR f2.fecha_emision <= p_fecha_hasta)
            ORDER BY f2.total DESC LIMIT 1
        )                                       AS numero_factura_mayor
    FROM repartidor rep
    JOIN persona p       ON p.id_persona      = rep.id_persona
    LEFT JOIN factura f  ON f.id_repartidor   = rep.id_repartidor
                         AND f.estado_factura != 'Anulada'
                         AND (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
                         AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta)
    LEFT JOIN recorrido_ruta rr ON rr.id_recorrido = f.id_recorrido
    LEFT JOIN ruta ru   ON ru.id_ruta = rr.id_ruta
    WHERE rep.estado_repartidor = 'Activo'
    GROUP BY rep.id_repartidor, p.nombre, rep.licencia, rep.estado_repartidor
    ORDER BY monto_total_vendido DESC;
END //

DELIMITER ;
