-- ============================================================
-- Procedimientos con Manejo de Transacciones (5)
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;
DELIMITER //

-- ============================================================
-- TRX-01: sp_trx_crear_factura_completa
-- Crea una factura completa (encabezado + detalles + subtype)
-- de forma atómica. Garantiza que si algún paso falla no
-- quede ningún registro parcial en la base de datos.
-- Accede a: factura, detalle_factura, lote,
--           factura_contado / factura_credito, venta
-- ============================================================
DROP PROCEDURE IF EXISTS sp_trx_crear_factura_completa //
CREATE PROCEDURE sp_trx_crear_factura_completa(
    IN  p_id_cliente       INT,
    IN  p_id_repartidor    INT,
    IN  p_id_recorrido     INT,
    IN  p_condicion_pago   VARCHAR(20),
    IN  p_id_presentacion  INT,
    IN  p_id_lote          INT,
    IN  p_cantidad         INT,
    IN  p_monto_recibido   DECIMAL(10,2),
    IN  p_fecha_venc_cred  DATE,
    IN  p_limite_credito   DECIMAL(10,2),
    OUT p_id_factura       INT,
    OUT p_numero_factura   VARCHAR(20),
    OUT p_mensaje          VARCHAR(255)
)
BEGIN
    DECLARE v_precio        DECIMAL(10,2) DEFAULT 0;
    DECLARE v_subtotal      DECIMAL(10,2) DEFAULT 0;
    DECLARE v_id_detalle    INT DEFAULT 0;
    DECLARE v_disp          INT DEFAULT 0;
    DECLARE v_seq           INT DEFAULT 0;
    DECLARE v_credito_ok    BOOLEAN DEFAULT FALSE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_mensaje = 'Error: transacción revertida.';
    END;

    START TRANSACTION;

    -- Validar stock disponible
    SELECT cantidad_disponible INTO v_disp FROM lote WHERE id_lote = p_id_lote FOR UPDATE;
    IF v_disp < p_cantidad THEN
        SET p_mensaje = 'Error: stock insuficiente en el lote seleccionado.';
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'stock_insuficiente';
    END IF;

    -- Validar crédito del cliente si aplica
    IF p_condicion_pago = 'Crédito' THEN
        SELECT credito_autorizado INTO v_credito_ok
        FROM cliente WHERE id_cliente = p_id_cliente;
        IF NOT v_credito_ok THEN
            SET p_mensaje = 'Error: el cliente no tiene crédito autorizado.';
            ROLLBACK;
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'credito_no_autorizado';
        END IF;
    END IF;

    -- Generar número de factura
    SELECT COUNT(*) + 1 INTO v_seq FROM factura;
    SET p_numero_factura = CONCAT('FAC-', LPAD(v_seq, 5, '0'));

    -- Insertar encabezado de factura
    INSERT INTO factura (id_cliente, id_repartidor, id_recorrido,
                         numero_factura, condicion_pago, total)
    VALUES (p_id_cliente, p_id_repartidor, p_id_recorrido,
            p_numero_factura, p_condicion_pago, 0.00);
    SET p_id_factura = LAST_INSERT_ID();

    -- Obtener precio de la presentación
    SELECT precio_venta INTO v_precio FROM presentacion WHERE id_presentacion = p_id_presentacion;
    SET v_subtotal = v_precio * p_cantidad;

    -- Insertar detalle
    INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote,
                                 cantidad, precio_unitario, subtotal)
    VALUES (p_id_factura, p_id_presentacion, p_id_lote,
            p_cantidad, v_precio, v_subtotal);
    SET v_id_detalle = LAST_INSERT_ID();

    -- Actualizar total de factura
    UPDATE factura SET total = v_subtotal WHERE id_factura = p_id_factura;

    -- Actualizar stock del lote
    UPDATE lote
    SET cantidad_disponible = cantidad_disponible - p_cantidad,
        estado_lote = IF(cantidad_disponible - p_cantidad = 0, 'Agotado', estado_lote)
    WHERE id_lote = p_id_lote;

    -- Registrar subtipo de factura
    IF p_condicion_pago = 'Contado' THEN
        INSERT INTO factura_contado (id_factura, monto_recibido, vuelto)
        VALUES (p_id_factura, p_monto_recibido, p_monto_recibido - v_subtotal);
        UPDATE factura SET estado_factura = 'Pagada' WHERE id_factura = p_id_factura;
    ELSE
        INSERT INTO factura_credito
            (id_factura, fecha_vencimiento_credito, limite_credito_aplicado, saldo_pendiente)
        VALUES (p_id_factura, p_fecha_venc_cred, p_limite_credito, v_subtotal);
        UPDATE factura SET estado_factura = 'Pendiente' WHERE id_factura = p_id_factura;
    END IF;

    -- Registrar en VENTA para reportes
    INSERT INTO venta (id_factura, id_detalle, tipo_venta)
    VALUES (p_id_factura, v_id_detalle, p_condicion_pago);

    COMMIT;
    SET p_mensaje = 'Factura creada exitosamente.';
END //

-- ============================================================
-- TRX-02: sp_trx_registrar_pago
-- Registra un pago parcial o total de una factura a crédito y
-- actualiza el saldo pendiente. Si el saldo llega a 0 marca
-- la factura como 'Pagada'. Accede a: pago, factura_credito, factura.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_trx_registrar_pago //
CREATE PROCEDURE sp_trx_registrar_pago(
    IN  p_id_factura_credito INT,
    IN  p_monto              DECIMAL(10,2),
    IN  p_metodo_pago        VARCHAR(20),
    IN  p_comprobante        VARCHAR(100),
    OUT p_id_pago            INT,
    OUT p_saldo_restante     DECIMAL(10,2),
    OUT p_mensaje            VARCHAR(255)
)
BEGIN
    DECLARE v_saldo_actual DECIMAL(10,2);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_mensaje = 'Error: pago no registrado.';
    END;

    START TRANSACTION;

    -- Bloquear el registro de crédito para actualización
    SELECT saldo_pendiente INTO v_saldo_actual
    FROM factura_credito WHERE id_factura = p_id_factura_credito FOR UPDATE;

    IF p_monto > v_saldo_actual THEN
        SET p_mensaje = 'Error: el monto excede el saldo pendiente.';
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'monto_excede_saldo';
    END IF;

    -- Registrar pago
    INSERT INTO pago (id_factura_credito, monto, metodo_pago, numero_comprobante)
    VALUES (p_id_factura_credito, p_monto, p_metodo_pago, p_comprobante);
    SET p_id_pago = LAST_INSERT_ID();

    -- Actualizar saldo pendiente
    UPDATE factura_credito
    SET saldo_pendiente = saldo_pendiente - p_monto
    WHERE id_factura = p_id_factura_credito;

    SET p_saldo_restante = v_saldo_actual - p_monto;

    -- Marcar factura como pagada si saldo llega a 0
    IF p_saldo_restante = 0 THEN
        UPDATE factura SET estado_factura = 'Pagada'
        WHERE id_factura = p_id_factura_credito;
    END IF;

    COMMIT;
    SET p_mensaje = IF(p_saldo_restante = 0,
        'Pago registrado. Factura cancelada por completo.',
        CONCAT('Pago registrado. Saldo restante: ', p_saldo_restante));
END //

-- ============================================================
-- TRX-03: sp_trx_crear_recorrido
-- Crea un recorrido verificando que el repartidor esté
-- asignado a la ruta y en estado Activo. Si no existe
-- asignación activa la crea automáticamente.
-- Accede a: recorrido_ruta, asignacion_ruta, repartidor, ruta.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_trx_crear_recorrido //
CREATE PROCEDURE sp_trx_crear_recorrido(
    IN  p_id_ruta       INT,
    IN  p_id_repartidor INT,
    IN  p_fecha         DATE,
    IN  p_turno         VARCHAR(20),
    OUT p_id_recorrido  INT,
    OUT p_mensaje       VARCHAR(255)
)
BEGIN
    DECLARE v_estado_rep VARCHAR(20);
    DECLARE v_estado_rut VARCHAR(20);
    DECLARE v_asig_activa INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_mensaje = 'Error al crear el recorrido.';
    END;

    START TRANSACTION;

    -- Verificar estado del repartidor
    SELECT estado_repartidor INTO v_estado_rep
    FROM repartidor WHERE id_repartidor = p_id_repartidor;
    IF v_estado_rep != 'Activo' THEN
        SET p_mensaje = 'Error: el repartidor no está activo.';
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'repartidor_inactivo';
    END IF;

    -- Verificar estado de la ruta
    SELECT estado_ruta INTO v_estado_rut FROM ruta WHERE id_ruta = p_id_ruta;
    IF v_estado_rut != 'Activa' THEN
        SET p_mensaje = 'Error: la ruta no está activa.';
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ruta_inactiva';
    END IF;

    -- Verificar o crear asignación activa
    SELECT COUNT(*) INTO v_asig_activa
    FROM asignacion_ruta
    WHERE id_ruta = p_id_ruta AND id_repartidor = p_id_repartidor AND fecha_fin IS NULL;

    IF v_asig_activa = 0 THEN
        INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio)
        VALUES (p_id_ruta, p_id_repartidor, CURRENT_DATE);
    END IF;

    -- Crear recorrido
    INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido)
    VALUES (p_id_ruta, p_id_repartidor,
            COALESCE(p_fecha, CURRENT_DATE), p_turno, 'Pendiente');
    SET p_id_recorrido = LAST_INSERT_ID();

    COMMIT;
    SET p_mensaje = 'Recorrido creado exitosamente.';
END //

-- ============================================================
-- TRX-04: sp_trx_registrar_producto_completo
-- Registra un producto con su primera presentación y lote
-- inicial en una sola transacción atómica.
-- Accede a: producto, presentacion, lote.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_trx_registrar_producto_completo //
CREATE PROCEDURE sp_trx_registrar_producto_completo(
    IN  p_nombre_comercial VARCHAR(100),
    IN  p_codigo_barras    VARCHAR(50),
    IN  p_categoria        VARCHAR(50),
    IN  p_tamano           VARCHAR(20),
    IN  p_unidad_medida    VARCHAR(10),
    IN  p_precio_venta     DECIMAL(10,2),
    IN  p_numero_lote      VARCHAR(50),
    IN  p_fecha_elab       DATE,
    IN  p_fecha_venc       DATE,
    IN  p_cantidad         INT,
    OUT p_id_producto      INT,
    OUT p_id_presentacion  INT,
    OUT p_id_lote          INT,
    OUT p_mensaje          VARCHAR(255)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_mensaje = 'Error: producto no registrado. Verifique duplicados.';
    END;

    START TRANSACTION;

    INSERT INTO producto (nombre_comercial, codigo_barras, categoria)
    VALUES (TRIM(p_nombre_comercial), TRIM(p_codigo_barras), p_categoria);
    SET p_id_producto = LAST_INSERT_ID();

    INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta)
    VALUES (p_id_producto, p_tamano, p_unidad_medida, p_precio_venta);
    SET p_id_presentacion = LAST_INSERT_ID();

    INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion,
                      fecha_vencimiento, cantidad_producida, cantidad_disponible)
    VALUES (p_id_producto, p_numero_lote, p_fecha_elab,
            p_fecha_venc, p_cantidad, p_cantidad);
    SET p_id_lote = LAST_INSERT_ID();

    COMMIT;
    SET p_mensaje = 'Producto, presentación y lote registrados exitosamente.';
END //

-- ============================================================
-- TRX-05: sp_trx_anular_factura
-- Anula una factura y restaura el stock de los lotes afectados.
-- Solo se puede anular si está en estado 'Emitida' o 'Pendiente'.
-- Accede a: factura, detalle_factura, lote, factura_credito.
-- ============================================================
DROP PROCEDURE IF EXISTS sp_trx_anular_factura //
CREATE PROCEDURE sp_trx_anular_factura(
    IN  p_id_factura INT,
    OUT p_mensaje    VARCHAR(255)
)
BEGIN
    DECLARE v_estado    VARCHAR(20);
    DECLARE v_cond_pago VARCHAR(20);
    DECLARE v_id_det    INT;
    DECLARE v_id_lote   INT;
    DECLARE v_cant      INT;
    DECLARE done        INT DEFAULT FALSE;

    DECLARE cur_detalles CURSOR FOR
        SELECT id_detalle, id_lote, cantidad
        FROM detalle_factura WHERE id_factura = p_id_factura;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_mensaje = 'Error al anular la factura.';
    END;

    START TRANSACTION;

    SELECT estado_factura, condicion_pago
    INTO v_estado, v_cond_pago
    FROM factura WHERE id_factura = p_id_factura FOR UPDATE;

    IF v_estado NOT IN ('Emitida', 'Pendiente') THEN
        SET p_mensaje = CONCAT('No se puede anular. Estado actual: ', v_estado);
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'estado_invalido';
    END IF;

    -- Restaurar stock de cada lote usando cursor
    OPEN cur_detalles;
    lotes_loop: LOOP
        FETCH cur_detalles INTO v_id_det, v_id_lote, v_cant;
        IF done THEN LEAVE lotes_loop; END IF;
        UPDATE lote
        SET cantidad_disponible = cantidad_disponible + v_cant,
            estado_lote = IF(estado_lote = 'Agotado', 'Disponible', estado_lote)
        WHERE id_lote = v_id_lote;
    END LOOP;
    CLOSE cur_detalles;

    -- Eliminar registro de crédito si aplica
    IF v_cond_pago = 'Crédito' THEN
        DELETE FROM pago WHERE id_factura_credito = p_id_factura;
        DELETE FROM factura_credito WHERE id_factura = p_id_factura;
    END IF;

    UPDATE factura SET estado_factura = 'Anulada' WHERE id_factura = p_id_factura;

    COMMIT;
    SET p_mensaje = 'Factura anulada y stock restaurado correctamente.';
END //

DELIMITER ;
