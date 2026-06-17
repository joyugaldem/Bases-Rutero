-- ============================================================
-- Cursores (2)
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;
DELIMITER //

-- ============================================================
-- CURSOR 1: sp_cur_actualizar_lotes_vencidos
-- Recorre todos los lotes en estado 'Disponible' cuya fecha
-- de vencimiento ya pasó y los marca como 'Vencido'.
-- Retorna la cantidad de lotes actualizados.
-- Accede a: lote, producto (JOIN para el log de salida).
-- ============================================================
DROP PROCEDURE IF EXISTS sp_cur_actualizar_lotes_vencidos //
CREATE PROCEDURE sp_cur_actualizar_lotes_vencidos(
    OUT p_lotes_actualizados INT
)
BEGIN
    DECLARE v_id_lote      INT;
    DECLARE v_numero_lote  VARCHAR(50);
    DECLARE v_nombre_prod  VARCHAR(100);
    DECLARE v_fecha_venc   DATE;
    DECLARE v_contador     INT DEFAULT 0;
    DECLARE done           INT DEFAULT FALSE;

    -- Cursor sobre lotes disponibles ya vencidos
    DECLARE cur_lotes CURSOR FOR
        SELECT l.id_lote, l.numero_lote, l.fecha_vencimiento, pd.nombre_comercial
        FROM lote l
        JOIN producto pd ON pd.id_producto = l.id_producto
        WHERE l.estado_lote = 'Disponible'
          AND l.fecha_vencimiento < CURRENT_DATE
        ORDER BY l.fecha_vencimiento;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur_lotes;

    actualizar_loop: LOOP
        FETCH cur_lotes INTO v_id_lote, v_numero_lote, v_fecha_venc, v_nombre_prod;
        IF done THEN
            LEAVE actualizar_loop;
        END IF;

        -- Marcar lote como vencido
        UPDATE lote SET estado_lote = 'Vencido' WHERE id_lote = v_id_lote;
        SET v_contador = v_contador + 1;
    END LOOP;

    CLOSE cur_lotes;
    SET p_lotes_actualizados = v_contador;
END //

-- ============================================================
-- CURSOR 2: sp_cur_resumen_creditos
-- Recorre todos los clientes que tienen al menos una factura
-- a crédito pendiente y calcula por cada uno: total adeudado,
-- cantidad de facturas pendientes y la factura más antigua.
-- Almacena el resultado en una tabla temporal para consulta.
-- Accede a: cliente, persona, factura, factura_credito, ruta.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_cur_resumen_creditos //
CREATE PROCEDURE sp_cur_resumen_creditos()
BEGIN
    DECLARE v_id_cliente    INT;
    DECLARE v_razon_social  VARCHAR(150);
    DECLARE v_nombre        VARCHAR(100);
    DECLARE v_ruta_nombre   VARCHAR(100);
    DECLARE v_total_deuda   DECIMAL(10,2);
    DECLARE v_cant_facturas INT;
    DECLARE v_fact_antigua  VARCHAR(20);
    DECLARE done            INT DEFAULT FALSE;

    -- Cursor sobre clientes con deudas activas
    DECLARE cur_clientes CURSOR FOR
        SELECT DISTINCT c.id_cliente, c.razon_social, p.nombre,
               COALESCE(ru.nombre, 'Sin ruta')
        FROM cliente c
        JOIN persona p ON p.id_persona = c.id_persona
        LEFT JOIN ruta ru ON ru.id_ruta = c.id_ruta
        WHERE EXISTS (
            SELECT 1 FROM factura f
            JOIN factura_credito fcc ON fcc.id_factura = f.id_factura
            WHERE f.id_cliente = c.id_cliente AND fcc.saldo_pendiente > 0
        )
        ORDER BY c.razon_social;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    -- Tabla temporal de resultados
    DROP TEMPORARY TABLE IF EXISTS tmp_resumen_creditos;
    CREATE TEMPORARY TABLE tmp_resumen_creditos (
        id_cliente     INT,
        razon_social   VARCHAR(150),
        nombre_contacto VARCHAR(100),
        ruta           VARCHAR(100),
        total_deuda    DECIMAL(10,2),
        facturas_pend  INT,
        factura_antigua VARCHAR(20),
        generado_en    DATETIME
    );

    OPEN cur_clientes;

    clientes_loop: LOOP
        FETCH cur_clientes INTO v_id_cliente, v_razon_social, v_nombre, v_ruta_nombre;
        IF done THEN
            LEAVE clientes_loop;
        END IF;

        -- Calcular totales del cliente
        SELECT SUM(fcc.saldo_pendiente), COUNT(f.id_factura),
               MIN(f.numero_factura)
        INTO v_total_deuda, v_cant_facturas, v_fact_antigua
        FROM factura f
        JOIN factura_credito fcc ON fcc.id_factura = f.id_factura
        WHERE f.id_cliente = v_id_cliente
          AND fcc.saldo_pendiente > 0;

        INSERT INTO tmp_resumen_creditos
            (id_cliente, razon_social, nombre_contacto, ruta,
             total_deuda, facturas_pend, factura_antigua, generado_en)
        VALUES
            (v_id_cliente, v_razon_social, v_nombre, v_ruta_nombre,
             v_total_deuda, v_cant_facturas, v_fact_antigua, NOW());
    END LOOP;

    CLOSE cur_clientes;

    -- Retornar el resumen
    SELECT * FROM tmp_resumen_creditos
    ORDER BY total_deuda DESC;
END //

DELIMITER ;
