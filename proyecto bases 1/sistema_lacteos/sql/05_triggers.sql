-- ============================================================
-- Triggers (3)
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;
DELIMITER //

-- ============================================================
-- TRIGGER 1: trg_detalle_after_insert
-- AFTER INSERT en DETALLE_FACTURA.
-- Actualiza automáticamente:
--   (a) factura.total sumando el subtotal del nuevo detalle.
--   (b) lote.cantidad_disponible descontando las unidades vendidas.
--   (c) lote.estado_lote a 'Agotado' si la disponibilidad llega a 0.
-- Garantiza RF-14, RF-15 y la integridad del inventario.
-- ============================================================
DROP TRIGGER IF EXISTS trg_detalle_after_insert //
CREATE TRIGGER trg_detalle_after_insert
AFTER INSERT ON detalle_factura
FOR EACH ROW
BEGIN
    -- Actualizar total de la factura (atributo derivado RF-15)
    UPDATE factura
    SET total = total + NEW.subtotal
    WHERE id_factura = NEW.id_factura;

    -- Descontar stock del lote (RF-04)
    UPDATE lote
    SET cantidad_disponible = cantidad_disponible - NEW.cantidad,
        estado_lote = IF(cantidad_disponible - NEW.cantidad <= 0, 'Agotado', estado_lote)
    WHERE id_lote = NEW.id_lote;
END //

-- ============================================================
-- TRIGGER 2: trg_pago_after_insert
-- AFTER INSERT en PAGO.
-- Actualiza factura_credito.saldo_pendiente restando el monto
-- del nuevo pago. Si el saldo llega a cero cambia el estado
-- de la factura a 'Pagada', cumpliendo RF-17.
-- Accede a: pago → factura_credito → factura.
-- ============================================================
DROP TRIGGER IF EXISTS trg_pago_after_insert //
CREATE TRIGGER trg_pago_after_insert
AFTER INSERT ON pago
FOR EACH ROW
BEGIN
    DECLARE v_nuevo_saldo DECIMAL(10,2);

    -- Actualizar saldo pendiente (atributo derivado RF-17)
    UPDATE factura_credito
    SET saldo_pendiente = saldo_pendiente - NEW.monto
    WHERE id_factura = NEW.id_factura_credito;

    -- Obtener saldo actualizado
    SELECT saldo_pendiente INTO v_nuevo_saldo
    FROM factura_credito WHERE id_factura = NEW.id_factura_credito;

    -- Marcar la factura como pagada si el saldo es 0
    IF v_nuevo_saldo <= 0 THEN
        UPDATE factura
        SET estado_factura = 'Pagada'
        WHERE id_factura = NEW.id_factura_credito;
        -- Asegura que el saldo no quede negativo por redondeo
        UPDATE factura_credito
        SET saldo_pendiente = 0
        WHERE id_factura = NEW.id_factura_credito;
    END IF;
END //

-- ============================================================
-- TRIGGER 3: trg_factura_credito_before_insert
-- BEFORE INSERT en FACTURA_CREDITO.
-- Valida que:
--   (a) El cliente asociado a la factura tenga credito_autorizado = TRUE.
--   (b) La fecha de vencimiento del crédito sea posterior a la emisión.
-- Implementa RF-11 a nivel de base de datos (capa de datos).
-- ============================================================
DROP TRIGGER IF EXISTS trg_factura_credito_before_insert //
CREATE TRIGGER trg_factura_credito_before_insert
BEFORE INSERT ON factura_credito
FOR EACH ROW
BEGIN
    DECLARE v_credito_ok  BOOLEAN;
    DECLARE v_fecha_emis  DATE;

    -- Verificar crédito autorizado del cliente
    SELECT c.credito_autorizado, f.fecha_emision
    INTO v_credito_ok, v_fecha_emis
    FROM factura f
    JOIN cliente c ON c.id_cliente = f.id_cliente
    WHERE f.id_factura = NEW.id_factura;

    IF NOT v_credito_ok THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'El cliente no tiene crédito autorizado para esta operación.';
    END IF;

    -- Verificar que la fecha de vencimiento del crédito sea posterior a la emisión
    IF NEW.fecha_vencimiento_credito <= v_fecha_emis THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'La fecha de vencimiento del crédito debe ser posterior a la fecha de emisión.';
    END IF;
END //

DELIMITER ;
