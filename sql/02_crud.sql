-- ============================================================
-- Procedimientos CRUD para todas las relaciones
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;
SET NAMES utf8mb4;
DELIMITER //

-- ============================================================
-- PERSONA (E-01)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_persona //
CREATE PROCEDURE sp_insertar_persona(
    IN p_nombre VARCHAR(100),
    OUT p_id_persona INT
)
BEGIN
    INSERT INTO persona (nombre) VALUES (TRIM(p_nombre));
    SET p_id_persona = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_persona //
CREATE PROCEDURE sp_modificar_persona(
    IN p_id_persona INT,
    IN p_nombre VARCHAR(100)
)
BEGIN
    UPDATE persona SET nombre = TRIM(p_nombre)
    WHERE id_persona = p_id_persona;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_persona //
CREATE PROCEDURE sp_eliminar_persona(
    IN p_id_persona INT
)
BEGIN
    -- RNF-04: No eliminar si tiene ventas (integridad referencial garantizada por FK RESTRICT)
    DELETE FROM persona WHERE id_persona = p_id_persona;
END //

DROP PROCEDURE IF EXISTS sp_consultar_personas //
CREATE PROCEDURE sp_consultar_personas(
    IN p_id_persona INT   -- NULL para traer todos
)
BEGIN
    SELECT p.id_persona, p.nombre
    FROM persona p
    WHERE (p_id_persona IS NULL OR p.id_persona = p_id_persona)
    ORDER BY p.nombre;
END //

-- ============================================================
-- TELEFONO_PERSONA (E-02)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_telefono //
CREATE PROCEDURE sp_insertar_telefono(
    IN p_id_persona   INT,
    IN p_telefono     VARCHAR(20),
    IN p_tipo         VARCHAR(20)
)
BEGIN
    INSERT INTO telefono_persona (id_persona, telefono, tipo_telefono)
    VALUES (p_id_persona, p_telefono, p_tipo);
END //

DROP PROCEDURE IF EXISTS sp_modificar_telefono //
CREATE PROCEDURE sp_modificar_telefono(
    IN p_id_persona  INT,
    IN p_tel_old     VARCHAR(20),
    IN p_tel_new     VARCHAR(20),
    IN p_tipo        VARCHAR(20)
)
BEGIN
    UPDATE telefono_persona
    SET telefono = p_tel_new, tipo_telefono = p_tipo
    WHERE id_persona = p_id_persona AND telefono = p_tel_old;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_telefono //
CREATE PROCEDURE sp_eliminar_telefono(
    IN p_id_persona INT,
    IN p_telefono   VARCHAR(20)
)
BEGIN
    DELETE FROM telefono_persona
    WHERE id_persona = p_id_persona AND telefono = p_telefono;
END //

DROP PROCEDURE IF EXISTS sp_consultar_telefonos //
CREATE PROCEDURE sp_consultar_telefonos(
    IN p_id_persona INT
)
BEGIN
    SELECT id_persona, telefono, tipo_telefono
    FROM telefono_persona
    WHERE id_persona = p_id_persona
    ORDER BY tipo_telefono, telefono;
END //

-- ============================================================
-- RUTA (E-05)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_ruta //
CREATE PROCEDURE sp_insertar_ruta(
    IN p_nombre         VARCHAR(100),
    IN p_zona           VARCHAR(100),
    IN p_descripcion    VARCHAR(255),
    OUT p_id_ruta       INT
)
BEGIN
    INSERT INTO ruta (nombre, zona_geografica, descripcion)
    VALUES (TRIM(p_nombre), TRIM(p_zona), p_descripcion);
    SET p_id_ruta = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_ruta //
CREATE PROCEDURE sp_modificar_ruta(
    IN p_id_ruta      INT,
    IN p_nombre       VARCHAR(100),
    IN p_zona         VARCHAR(100),
    IN p_descripcion  VARCHAR(255),
    IN p_estado       VARCHAR(20)
)
BEGIN
    UPDATE ruta
    SET nombre = TRIM(p_nombre),
        zona_geografica = TRIM(p_zona),
        descripcion = p_descripcion,
        estado_ruta = p_estado
    WHERE id_ruta = p_id_ruta;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_ruta //
CREATE PROCEDURE sp_eliminar_ruta(IN p_id_ruta INT)
BEGIN
    UPDATE ruta SET estado_ruta = 'Inactiva' WHERE id_ruta = p_id_ruta;
END //

DROP PROCEDURE IF EXISTS sp_consultar_rutas //
CREATE PROCEDURE sp_consultar_rutas(IN p_id_ruta INT)
BEGIN
    SELECT id_ruta, nombre, zona_geografica, descripcion, estado_ruta
    FROM ruta
    WHERE (p_id_ruta IS NULL OR id_ruta = p_id_ruta)
    ORDER BY nombre;
END //

-- ============================================================
-- CLIENTE (E-03)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_cliente //
CREATE PROCEDURE sp_insertar_cliente(
    IN  p_nombre        VARCHAR(100),
    IN  p_razon_social  VARCHAR(150),
    IN  p_direccion     VARCHAR(500),
    IN  p_credito       BOOLEAN,
    IN  p_id_ruta       INT,
    OUT p_id_cliente    INT,
    OUT p_id_persona    INT
)
BEGIN
    DECLARE v_id_persona INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_id_cliente = NULL;
        SET p_id_persona = NULL;
    END;

    START TRANSACTION;
    CALL sp_insertar_persona(p_nombre, v_id_persona);
    INSERT INTO cliente (id_persona, id_ruta, razon_social, direccion_compuesta, credito_autorizado)
    VALUES (v_id_persona, p_id_ruta, TRIM(p_razon_social), p_direccion, p_credito);
    SET p_id_cliente = LAST_INSERT_ID();
    SET p_id_persona = v_id_persona;
    COMMIT;
END //

DROP PROCEDURE IF EXISTS sp_modificar_cliente //
CREATE PROCEDURE sp_modificar_cliente(
    IN p_id_cliente   INT,
    IN p_nombre       VARCHAR(100),
    IN p_razon_social VARCHAR(150),
    IN p_direccion    VARCHAR(500),
    IN p_credito      BOOLEAN,
    IN p_id_ruta      INT,
    IN p_estado       VARCHAR(20)
)
BEGIN
    DECLARE v_id_persona INT;
    SELECT id_persona INTO v_id_persona FROM cliente WHERE id_cliente = p_id_cliente;
    UPDATE persona SET nombre = TRIM(p_nombre) WHERE id_persona = v_id_persona;
    UPDATE cliente
    SET razon_social       = TRIM(p_razon_social),
        direccion_compuesta = p_direccion,
        credito_autorizado  = p_credito,
        id_ruta             = p_id_ruta,
        estado_cliente      = p_estado
    WHERE id_cliente = p_id_cliente;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_cliente //
CREATE PROCEDURE sp_eliminar_cliente(IN p_id_cliente INT)
BEGIN
    -- Borrado físico si no tiene facturas; lógico si las tiene (RNF-04)
    IF EXISTS (SELECT 1 FROM factura WHERE id_cliente = p_id_cliente LIMIT 1) THEN
        UPDATE cliente SET estado_cliente = 'Inactivo' WHERE id_cliente = p_id_cliente;
    ELSE
        DELETE FROM cliente WHERE id_cliente = p_id_cliente;
    END IF;
END //

DROP PROCEDURE IF EXISTS sp_consultar_clientes //
CREATE PROCEDURE sp_consultar_clientes(IN p_id_cliente INT)
BEGIN
    SELECT c.id_cliente, c.id_persona, p.nombre, c.razon_social, c.direccion_compuesta,
           c.credito_autorizado, c.estado_cliente,
           r.nombre AS ruta_nombre, r.zona_geografica
    FROM cliente c
    JOIN persona p ON p.id_persona = c.id_persona
    LEFT JOIN ruta r ON r.id_ruta = c.id_ruta
    WHERE (p_id_cliente IS NULL OR c.id_cliente = p_id_cliente)
    ORDER BY c.razon_social;
END //

-- ============================================================
-- REPARTIDOR (E-04)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_repartidor //
CREATE PROCEDURE sp_insertar_repartidor(
    IN p_nombre        VARCHAR(100),
    IN p_licencia      VARCHAR(20),
    OUT p_id_repartidor INT
)
BEGIN
    DECLARE v_id_persona INT;
    CALL sp_insertar_persona(p_nombre, v_id_persona);
    INSERT INTO repartidor (id_persona, licencia)
    VALUES (v_id_persona, TRIM(p_licencia));
    SET p_id_repartidor = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_repartidor //
CREATE PROCEDURE sp_modificar_repartidor(
    IN p_id_repartidor INT,
    IN p_nombre        VARCHAR(100),
    IN p_licencia      VARCHAR(20),
    IN p_estado        VARCHAR(20)
)
BEGIN
    DECLARE v_id_persona INT;
    SELECT id_persona INTO v_id_persona FROM repartidor WHERE id_repartidor = p_id_repartidor;
    UPDATE persona SET nombre = TRIM(p_nombre) WHERE id_persona = v_id_persona;
    UPDATE repartidor
    SET licencia = TRIM(p_licencia), estado_repartidor = p_estado
    WHERE id_repartidor = p_id_repartidor;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_repartidor //
CREATE PROCEDURE sp_eliminar_repartidor(IN p_id_repartidor INT)
BEGIN
    UPDATE repartidor SET estado_repartidor = 'Inactivo' WHERE id_repartidor = p_id_repartidor;
END //

DROP PROCEDURE IF EXISTS sp_consultar_repartidores //
CREATE PROCEDURE sp_consultar_repartidores(IN p_id_repartidor INT)
BEGIN
    SELECT r.id_repartidor, p.nombre, r.licencia, r.estado_repartidor
    FROM repartidor r
    JOIN persona p ON p.id_persona = r.id_persona
    WHERE (p_id_repartidor IS NULL OR r.id_repartidor = p_id_repartidor)
    ORDER BY p.nombre;
END //

-- ============================================================
-- ASIGNACION_RUTA (E-06)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_asignacion //
CREATE PROCEDURE sp_insertar_asignacion(
    IN p_id_ruta       INT,
    IN p_id_repartidor INT,
    IN p_fecha_inicio  DATE,
    IN p_observacion   VARCHAR(255),
    OUT p_id_asignacion INT
)
BEGIN
    INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio, observacion)
    VALUES (p_id_ruta, p_id_repartidor, COALESCE(p_fecha_inicio, CURRENT_DATE), p_observacion);
    SET p_id_asignacion = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_asignacion //
CREATE PROCEDURE sp_modificar_asignacion(
    IN p_id_asignacion INT,
    IN p_fecha_fin     DATE,
    IN p_observacion   VARCHAR(255)
)
BEGIN
    UPDATE asignacion_ruta
    SET fecha_fin = p_fecha_fin, observacion = p_observacion
    WHERE id_asignacion = p_id_asignacion;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_asignacion //
CREATE PROCEDURE sp_eliminar_asignacion(IN p_id_asignacion INT)
BEGIN
    DELETE FROM asignacion_ruta WHERE id_asignacion = p_id_asignacion;
END //

DROP PROCEDURE IF EXISTS sp_consultar_asignaciones //
CREATE PROCEDURE sp_consultar_asignaciones(IN p_id_ruta INT, IN p_id_repartidor INT)
BEGIN
    SELECT a.id_asignacion, r.nombre AS ruta, p.nombre AS repartidor,
           a.fecha_inicio, a.fecha_fin, a.observacion
    FROM asignacion_ruta a
    JOIN ruta r ON r.id_ruta = a.id_ruta
    JOIN repartidor rep ON rep.id_repartidor = a.id_repartidor
    JOIN persona p ON p.id_persona = rep.id_persona
    WHERE (p_id_ruta IS NULL OR a.id_ruta = p_id_ruta)
      AND (p_id_repartidor IS NULL OR a.id_repartidor = p_id_repartidor)
    ORDER BY a.fecha_inicio DESC;
END //

-- ============================================================
-- RECORRIDO_RUTA (E-07)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_recorrido //
CREATE PROCEDURE sp_insertar_recorrido(
    IN p_id_ruta       INT,
    IN p_id_repartidor INT,
    IN p_fecha         DATE,
    IN p_turno         VARCHAR(20),
    IN p_observacion   VARCHAR(255),
    OUT p_id_recorrido INT
)
BEGIN
    INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, observacion)
    VALUES (p_id_ruta, p_id_repartidor,
            COALESCE(p_fecha, CURRENT_DATE), p_turno, p_observacion);
    SET p_id_recorrido = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_recorrido //
CREATE PROCEDURE sp_modificar_recorrido(
    IN p_id_recorrido    INT,
    IN p_estado          VARCHAR(20),
    IN p_observacion     VARCHAR(255)
)
BEGIN
    UPDATE recorrido_ruta
    SET estado_recorrido = p_estado, observacion = p_observacion
    WHERE id_recorrido = p_id_recorrido;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_recorrido //
CREATE PROCEDURE sp_eliminar_recorrido(IN p_id_recorrido INT)
BEGIN
    UPDATE recorrido_ruta
    SET estado_recorrido = 'Cancelado'
    WHERE id_recorrido = p_id_recorrido;
END //

DROP PROCEDURE IF EXISTS sp_consultar_recorridos //
CREATE PROCEDURE sp_consultar_recorridos(IN p_id_ruta INT, IN p_fecha DATE)
BEGIN
    SELECT rr.id_recorrido, ru.nombre AS ruta, p.nombre AS repartidor,
           rr.fecha, rr.turno, rr.estado_recorrido, rr.observacion
    FROM recorrido_ruta rr
    JOIN ruta ru ON ru.id_ruta = rr.id_ruta
    JOIN repartidor rep ON rep.id_repartidor = rr.id_repartidor
    JOIN persona p ON p.id_persona = rep.id_persona
    WHERE (p_id_ruta IS NULL OR rr.id_ruta = p_id_ruta)
      AND (p_fecha IS NULL OR rr.fecha = p_fecha)
    ORDER BY rr.fecha DESC, rr.turno;
END //

-- ============================================================
-- PRODUCTO (E-08)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_producto //
CREATE PROCEDURE sp_insertar_producto(
    IN p_nombre        VARCHAR(100),
    IN p_cod_barras    VARCHAR(50),
    IN p_categoria     VARCHAR(50),
    OUT p_id_producto  INT
)
BEGIN
    INSERT INTO producto (nombre_comercial, codigo_barras, categoria)
    VALUES (TRIM(p_nombre), TRIM(p_cod_barras), p_categoria);
    SET p_id_producto = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_producto //
CREATE PROCEDURE sp_modificar_producto(
    IN p_id_producto   INT,
    IN p_nombre        VARCHAR(100),
    IN p_cod_barras    VARCHAR(50),
    IN p_categoria     VARCHAR(50),
    IN p_estado        VARCHAR(20)
)
BEGIN
    UPDATE producto
    SET nombre_comercial = TRIM(p_nombre),
        codigo_barras    = TRIM(p_cod_barras),
        categoria        = p_categoria,
        estado_producto  = p_estado
    WHERE id_producto = p_id_producto;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_producto //
CREATE PROCEDURE sp_eliminar_producto(IN p_id_producto INT)
BEGIN
    -- RNF-04: borrado lógico si hay ventas, físico solo si no las hay
    IF EXISTS (SELECT 1 FROM detalle_factura df
               JOIN presentacion pr ON pr.id_presentacion = df.id_presentacion
               WHERE pr.id_producto = p_id_producto LIMIT 1) THEN
        UPDATE producto SET estado_producto = 'Descontinuado' WHERE id_producto = p_id_producto;
    ELSE
        DELETE FROM producto WHERE id_producto = p_id_producto;
    END IF;
END //

DROP PROCEDURE IF EXISTS sp_consultar_productos //
CREATE PROCEDURE sp_consultar_productos(IN p_id_producto INT)
BEGIN
    SELECT id_producto, nombre_comercial, codigo_barras, categoria, estado_producto
    FROM producto
    WHERE (p_id_producto IS NULL OR id_producto = p_id_producto)
    ORDER BY nombre_comercial;
END //

-- ============================================================
-- PRESENTACION (E-09)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_presentacion //
CREATE PROCEDURE sp_insertar_presentacion(
    IN p_id_producto      INT,
    IN p_tamano           VARCHAR(20),
    IN p_unidad           VARCHAR(10),
    IN p_precio           DECIMAL(10,2),
    IN p_descripcion      VARCHAR(255),
    OUT p_id_presentacion INT
)
BEGIN
    INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta, descripcion)
    VALUES (p_id_producto, p_tamano, p_unidad, p_precio, p_descripcion);
    SET p_id_presentacion = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_presentacion //
CREATE PROCEDURE sp_modificar_presentacion(
    IN p_id_presentacion INT,
    IN p_tamano          VARCHAR(20),
    IN p_unidad          VARCHAR(10),
    IN p_precio          DECIMAL(10,2),
    IN p_descripcion     VARCHAR(255),
    IN p_estado          VARCHAR(20)
)
BEGIN
    UPDATE presentacion
    SET tamano = p_tamano, unidad_medida = p_unidad,
        precio_venta = p_precio, descripcion = p_descripcion,
        estado_presentacion = p_estado
    WHERE id_presentacion = p_id_presentacion;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_presentacion //
CREATE PROCEDURE sp_eliminar_presentacion(IN p_id_presentacion INT)
BEGIN
    IF EXISTS (SELECT 1 FROM detalle_factura WHERE id_presentacion = p_id_presentacion LIMIT 1) THEN
        UPDATE presentacion SET estado_presentacion = 'Inactiva'
        WHERE id_presentacion = p_id_presentacion;
    ELSE
        DELETE FROM presentacion WHERE id_presentacion = p_id_presentacion;
    END IF;
END //

DROP PROCEDURE IF EXISTS sp_consultar_presentaciones //
CREATE PROCEDURE sp_consultar_presentaciones(IN p_id_producto INT)
BEGIN
    SELECT pr.id_presentacion, pd.nombre_comercial, pr.tamano,
           pr.unidad_medida, pr.precio_venta, pr.descripcion, pr.estado_presentacion
    FROM presentacion pr
    JOIN producto pd ON pd.id_producto = pr.id_producto
    WHERE (p_id_producto IS NULL OR pr.id_producto = p_id_producto)
    ORDER BY pd.nombre_comercial, pr.tamano;
END //

-- ============================================================
-- LOTE (E-10)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_lote //
CREATE PROCEDURE sp_insertar_lote(
    IN p_id_producto   INT,
    IN p_numero_lote   VARCHAR(50),
    IN p_fecha_elab    DATE,
    IN p_fecha_venc    DATE,
    IN p_cant_prod     INT,
    OUT p_id_lote      INT
)
BEGIN
    INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion,
                      fecha_vencimiento, cantidad_producida, cantidad_disponible)
    VALUES (p_id_producto, p_numero_lote, p_fecha_elab,
            p_fecha_venc, p_cant_prod, p_cant_prod);
    SET p_id_lote = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_lote //
CREATE PROCEDURE sp_modificar_lote(
    IN p_id_lote       INT,
    IN p_cant_disp     INT,
    IN p_estado        VARCHAR(20)
)
BEGIN
    UPDATE lote
    SET cantidad_disponible = p_cant_disp, estado_lote = p_estado
    WHERE id_lote = p_id_lote;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_lote //
CREATE PROCEDURE sp_eliminar_lote(IN p_id_lote INT)
BEGIN
    IF EXISTS (SELECT 1 FROM detalle_factura WHERE id_lote = p_id_lote LIMIT 1) THEN
        UPDATE lote SET estado_lote = 'Retirado' WHERE id_lote = p_id_lote;
    ELSE
        DELETE FROM lote WHERE id_lote = p_id_lote;
    END IF;
END //

DROP PROCEDURE IF EXISTS sp_consultar_lotes //
CREATE PROCEDURE sp_consultar_lotes(IN p_id_producto INT)
BEGIN
    SELECT l.id_lote, pd.nombre_comercial, l.numero_lote,
           l.fecha_elaboracion, l.fecha_vencimiento,
           l.cantidad_producida, l.cantidad_disponible, l.estado_lote
    FROM lote l
    JOIN producto pd ON pd.id_producto = l.id_producto
    WHERE (p_id_producto IS NULL OR l.id_producto = p_id_producto)
    ORDER BY l.fecha_vencimiento;
END //

-- ============================================================
-- FACTURA (E-11)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_factura //
CREATE PROCEDURE sp_insertar_factura(
    IN p_id_cliente     INT,
    IN p_id_repartidor  INT,
    IN p_id_recorrido   INT,
    IN p_condicion_pago VARCHAR(20),
    OUT p_id_factura    INT,
    OUT p_numero_factura VARCHAR(20)
)
BEGIN
    DECLARE v_seq INT;
    SELECT COUNT(*) + 1 INTO v_seq FROM factura;
    SET p_numero_factura = CONCAT('FAC-', LPAD(v_seq, 5, '0'));
    INSERT INTO factura (id_cliente, id_repartidor, id_recorrido,
                         numero_factura, condicion_pago, total)
    VALUES (p_id_cliente, p_id_repartidor, p_id_recorrido,
            p_numero_factura, p_condicion_pago, 0.00);
    SET p_id_factura = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_factura //
CREATE PROCEDURE sp_modificar_factura(
    IN p_id_factura INT,
    IN p_estado     VARCHAR(20)
)
BEGIN
    UPDATE factura SET estado_factura = p_estado WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_factura //
CREATE PROCEDURE sp_eliminar_factura(IN p_id_factura INT)
BEGIN
    -- Anulación lógica solamente
    UPDATE factura SET estado_factura = 'Anulada' WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_consultar_facturas //
CREATE PROCEDURE sp_consultar_facturas(
    IN p_id_cliente    INT,
    IN p_fecha_desde   DATE,
    IN p_fecha_hasta   DATE
)
BEGIN
    SELECT f.id_factura, f.numero_factura, c.razon_social AS cliente,
           p.nombre AS repartidor, f.fecha_emision,
           f.condicion_pago, f.estado_factura, f.total,
           ru.nombre AS ruta
    FROM factura f
    JOIN cliente c ON c.id_cliente = f.id_cliente
    JOIN repartidor rep ON rep.id_repartidor = f.id_repartidor
    JOIN persona p ON p.id_persona = rep.id_persona
    JOIN recorrido_ruta rr ON rr.id_recorrido = f.id_recorrido
    JOIN ruta ru ON ru.id_ruta = rr.id_ruta
    WHERE (p_id_cliente IS NULL OR f.id_cliente = p_id_cliente)
      AND (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta)
    ORDER BY f.fecha_emision DESC;
END //

-- ============================================================
-- DETALLE_FACTURA (E-12)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_detalle //
CREATE PROCEDURE sp_insertar_detalle(
    IN p_id_factura     INT,
    IN p_id_presentacion INT,
    IN p_id_lote        INT,
    IN p_cantidad       INT,
    IN p_observacion    VARCHAR(255),
    OUT p_id_detalle    INT
)
BEGIN
    DECLARE v_precio DECIMAL(10,2);
    SELECT precio_venta INTO v_precio
    FROM presentacion WHERE id_presentacion = p_id_presentacion;
    INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote,
                                 cantidad, precio_unitario, subtotal, observacion)
    VALUES (p_id_factura, p_id_presentacion, p_id_lote,
            p_cantidad, v_precio, v_precio * p_cantidad, p_observacion);
    SET p_id_detalle = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_detalle //
CREATE PROCEDURE sp_modificar_detalle(
    IN p_id_detalle INT,
    IN p_cantidad   INT,
    IN p_obs        VARCHAR(255)
)
BEGIN
    DECLARE v_precio DECIMAL(10,2);
    SELECT precio_unitario INTO v_precio FROM detalle_factura WHERE id_detalle = p_id_detalle;
    UPDATE detalle_factura
    SET cantidad = p_cantidad, subtotal = v_precio * p_cantidad, observacion = p_obs
    WHERE id_detalle = p_id_detalle;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_detalle //
CREATE PROCEDURE sp_eliminar_detalle(IN p_id_detalle INT)
BEGIN
    DELETE FROM detalle_factura WHERE id_detalle = p_id_detalle;
END //

DROP PROCEDURE IF EXISTS sp_consultar_detalles //
CREATE PROCEDURE sp_consultar_detalles(IN p_id_factura INT)
BEGIN
    SELECT df.id_detalle, pd.nombre_comercial, pr.tamano, pr.unidad_medida,
           l.numero_lote, df.cantidad, df.precio_unitario, df.subtotal, df.observacion
    FROM detalle_factura df
    JOIN presentacion pr ON pr.id_presentacion = df.id_presentacion
    JOIN producto pd ON pd.id_producto = pr.id_producto
    JOIN lote l ON l.id_lote = df.id_lote
    WHERE df.id_factura = p_id_factura
    ORDER BY df.id_detalle;
END //

-- ============================================================
-- FACTURA_CONTADO (E-13)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_factura_contado //
CREATE PROCEDURE sp_insertar_factura_contado(
    IN p_id_factura    INT,
    IN p_monto_recibido DECIMAL(10,2)
)
BEGIN
    DECLARE v_total DECIMAL(10,2);
    SELECT total INTO v_total FROM factura WHERE id_factura = p_id_factura;
    INSERT INTO factura_contado (id_factura, monto_recibido, vuelto)
    VALUES (p_id_factura, p_monto_recibido, p_monto_recibido - v_total);
    UPDATE factura SET estado_factura = 'Pagada' WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_modificar_factura_contado //
CREATE PROCEDURE sp_modificar_factura_contado(
    IN p_id_factura     INT,
    IN p_monto_recibido DECIMAL(10,2)
)
BEGIN
    DECLARE v_total DECIMAL(10,2);
    SELECT total INTO v_total FROM factura WHERE id_factura = p_id_factura;
    UPDATE factura_contado
    SET monto_recibido = p_monto_recibido, vuelto = p_monto_recibido - v_total
    WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_factura_contado //
CREATE PROCEDURE sp_eliminar_factura_contado(IN p_id_factura INT)
BEGIN
    DELETE FROM factura_contado WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_consultar_factura_contado //
CREATE PROCEDURE sp_consultar_factura_contado(IN p_id_factura INT)
BEGIN
    SELECT fc.id_factura, f.numero_factura, f.total,
           fc.monto_recibido, fc.vuelto
    FROM factura_contado fc
    JOIN factura f ON f.id_factura = fc.id_factura
    WHERE fc.id_factura = p_id_factura;
END //

-- ============================================================
-- FACTURA_CREDITO (E-14)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_factura_credito //
CREATE PROCEDURE sp_insertar_factura_credito(
    IN p_id_factura            INT,
    IN p_fecha_vencimiento     DATE,
    IN p_limite_credito        DECIMAL(10,2)
)
BEGIN
    DECLARE v_total DECIMAL(10,2);
    SELECT total INTO v_total FROM factura WHERE id_factura = p_id_factura;
    INSERT INTO factura_credito
        (id_factura, fecha_vencimiento_credito, limite_credito_aplicado, saldo_pendiente)
    VALUES (p_id_factura, p_fecha_vencimiento, p_limite_credito, v_total);
    UPDATE factura SET estado_factura = 'Pendiente' WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_modificar_factura_credito //
CREATE PROCEDURE sp_modificar_factura_credito(
    IN p_id_factura        INT,
    IN p_fecha_vencimiento DATE
)
BEGIN
    UPDATE factura_credito
    SET fecha_vencimiento_credito = p_fecha_vencimiento
    WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_factura_credito //
CREATE PROCEDURE sp_eliminar_factura_credito(IN p_id_factura INT)
BEGIN
    DELETE FROM factura_credito WHERE id_factura = p_id_factura;
END //

DROP PROCEDURE IF EXISTS sp_consultar_factura_credito //
CREATE PROCEDURE sp_consultar_factura_credito(IN p_id_factura INT)
BEGIN
    SELECT fcc.id_factura, f.numero_factura, c.razon_social,
           f.total, fcc.saldo_pendiente,
           fcc.fecha_vencimiento_credito, fcc.limite_credito_aplicado
    FROM factura_credito fcc
    JOIN factura f ON f.id_factura = fcc.id_factura
    JOIN cliente c ON c.id_cliente = f.id_cliente
    WHERE (p_id_factura IS NULL OR fcc.id_factura = p_id_factura)
    ORDER BY fcc.fecha_vencimiento_credito;
END //

-- ============================================================
-- PAGO (E-15)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_pago //
CREATE PROCEDURE sp_insertar_pago(
    IN p_id_factura_credito INT,
    IN p_monto              DECIMAL(10,2),
    IN p_metodo_pago        VARCHAR(20),
    IN p_comprobante        VARCHAR(100),
    OUT p_id_pago           INT
)
BEGIN
    INSERT INTO pago (id_factura_credito, monto, metodo_pago, numero_comprobante)
    VALUES (p_id_factura_credito, p_monto, p_metodo_pago, p_comprobante);
    SET p_id_pago = LAST_INSERT_ID();
END //

DROP PROCEDURE IF EXISTS sp_modificar_pago //
CREATE PROCEDURE sp_modificar_pago(
    IN p_id_pago     INT,
    IN p_monto       DECIMAL(10,2),
    IN p_metodo_pago VARCHAR(20),
    IN p_comprobante VARCHAR(100)
)
BEGIN
    UPDATE pago
    SET monto = p_monto, metodo_pago = p_metodo_pago,
        numero_comprobante = p_comprobante
    WHERE id_pago = p_id_pago;
END //

DROP PROCEDURE IF EXISTS sp_eliminar_pago //
CREATE PROCEDURE sp_eliminar_pago(IN p_id_pago INT)
BEGIN
    DELETE FROM pago WHERE id_pago = p_id_pago;
END //

DROP PROCEDURE IF EXISTS sp_consultar_pagos //
CREATE PROCEDURE sp_consultar_pagos(IN p_id_factura_credito INT)
BEGIN
    SELECT pg.id_pago, f.numero_factura, pg.fecha_pago,
           pg.monto, pg.metodo_pago, pg.numero_comprobante
    FROM pago pg
    JOIN factura_credito fcc ON fcc.id_factura = pg.id_factura_credito
    JOIN factura f ON f.id_factura = fcc.id_factura
    WHERE (p_id_factura_credito IS NULL OR pg.id_factura_credito = p_id_factura_credito)
    ORDER BY pg.fecha_pago;
END //

-- ============================================================
-- VENTA (E-16)
-- ============================================================
DROP PROCEDURE IF EXISTS sp_insertar_venta //
CREATE PROCEDURE sp_insertar_venta(
    IN p_id_factura  INT,
    IN p_id_detalle  INT,
    IN p_tipo_venta  VARCHAR(20)
)
BEGIN
    INSERT INTO venta (id_factura, id_detalle, tipo_venta)
    VALUES (p_id_factura, p_id_detalle, p_tipo_venta);
END //

DROP PROCEDURE IF EXISTS sp_eliminar_venta //
CREATE PROCEDURE sp_eliminar_venta(IN p_id_venta INT)
BEGIN
    DELETE FROM venta WHERE id_venta = p_id_venta;
END //

DROP PROCEDURE IF EXISTS sp_consultar_ventas //
CREATE PROCEDURE sp_consultar_ventas(
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE
)
BEGIN
    SELECT v.id_venta, f.numero_factura, c.razon_social,
           pd.nombre_comercial, pr.tamano, pr.unidad_medida,
           df.cantidad, df.subtotal, v.tipo_venta, f.fecha_emision
    FROM venta v
    JOIN factura f ON f.id_factura = v.id_factura
    JOIN cliente c ON c.id_cliente = f.id_cliente
    JOIN detalle_factura df ON df.id_detalle = v.id_detalle
    JOIN presentacion pr ON pr.id_presentacion = df.id_presentacion
    JOIN producto pd ON pd.id_producto = pr.id_producto
    WHERE (p_fecha_desde IS NULL OR f.fecha_emision >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR f.fecha_emision <= p_fecha_hasta)
    ORDER BY f.fecha_emision DESC;
END //

DELIMITER ;
