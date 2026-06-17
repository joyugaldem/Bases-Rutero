-- ============================================================
-- Sistema de Facturación y Control de Ventas para Rutero
-- Productos Lácteos María del Carmen
-- Bases de Datos I – I Sem 2026
-- TEC – Tecnológico de Costa Rica
-- Autores: Joseph Fonseca, Joyce Ugalde, Kenneth Fernández
-- ============================================================

CREATE DATABASE IF NOT EXISTS lacteosdb
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_spanish_ci;

USE lacteosdb;
SET NAMES utf8mb4;

-- ============================================================
-- SECCIÓN 1: TIPOS DE DATOS CON REGLA ESPECÍFICA (TD)
-- En MySQL/MariaDB los dominios se implementan mediante
-- restricciones CHECK y columnas ENUM.
--
-- TD-01 tipo_monto      DECIMAL(10,2) CHECK(v > 0 AND v <= 9999999.99)
-- TD-02 tipo_estado     ENUM('Activo','Inactivo','Suspendido')
-- TD-03 tipo_cantidad   INT           CHECK(v > 0)
-- TD-04 tipo_telefono   VARCHAR(20)   CHECK(REGEXP '^[0-9+\-() ]{7,20}$')
-- TD-05 tipo_cod_barras VARCHAR(50)   CHECK(LENGTH > 0 AND NO SPACES)
-- ============================================================

-- ============================================================
-- SECCIÓN 2: VALORES POR DEFECTO (VD)
-- VD-01  estado_cliente      DEFAULT 'Activo'
-- VD-02  credito_autorizado  DEFAULT FALSE
-- VD-03  fecha_emision       DEFAULT (CURRENT_DATE)
-- VD-04  condicion_pago      DEFAULT 'Contado'
-- VD-05  estado_recorrido    DEFAULT 'Pendiente'
-- ============================================================

-- ============================================================
-- TABLAS
-- ============================================================

-- -------------------------------------------------------
-- E-01: PERSONA  (entidad raíz de la jerarquía)
-- -------------------------------------------------------
DROP TABLE IF EXISTS venta;
DROP TABLE IF EXISTS pago;
DROP TABLE IF EXISTS factura_credito;
DROP TABLE IF EXISTS factura_contado;
DROP TABLE IF EXISTS detalle_factura;
DROP TABLE IF EXISTS factura;
DROP TABLE IF EXISTS lote;
DROP TABLE IF EXISTS presentacion;
DROP TABLE IF EXISTS producto;
DROP TABLE IF EXISTS recorrido_ruta;
DROP TABLE IF EXISTS asignacion_ruta;
DROP TABLE IF EXISTS repartidor;
DROP TABLE IF EXISTS cliente;
DROP TABLE IF EXISTS ruta;
DROP TABLE IF EXISTS telefono_persona;
DROP TABLE IF EXISTS persona;

CREATE TABLE persona (
    id_persona   INT          NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(100) NOT NULL,
    CONSTRAINT pk_persona  PRIMARY KEY (id_persona),
    CONSTRAINT chk_persona_nombre CHECK (LENGTH(TRIM(nombre)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-02: TELEFONO_PERSONA  (débil-EX respecto a PERSONA)
-- TD-04: tipo_telefono aplicado al campo telefono
-- -------------------------------------------------------
CREATE TABLE telefono_persona (
    id_persona   INT         NOT NULL,
    telefono     VARCHAR(20) NOT NULL,
    tipo_telefono ENUM('Móvil','Fijo','WhatsApp') NOT NULL DEFAULT 'Móvil',
    CONSTRAINT pk_telefono_persona PRIMARY KEY (id_persona, telefono),
    CONSTRAINT fk_telp_persona FOREIGN KEY (id_persona)
        REFERENCES persona(id_persona) ON DELETE CASCADE ON UPDATE CASCADE,
    -- TD-04: tipo_telefono — exactamente 8 dígitos con guion: XXXX-XXXX
    CONSTRAINT chk_telefono_formato CHECK (telefono REGEXP '^[0-9]{4}-[0-9]{4}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-05: RUTA  (se crea antes que CLIENTE para FK)
-- -------------------------------------------------------
CREATE TABLE ruta (
    id_ruta        INT          NOT NULL AUTO_INCREMENT,
    nombre         VARCHAR(100) NOT NULL,
    zona_geografica VARCHAR(100) NOT NULL,
    descripcion    VARCHAR(255) DEFAULT NULL,
    estado_ruta    ENUM('Activa','Inactiva','Suspendida') NOT NULL DEFAULT 'Activa',
    CONSTRAINT pk_ruta PRIMARY KEY (id_ruta),
    CONSTRAINT chk_ruta_nombre CHECK (LENGTH(TRIM(nombre)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-03: CLIENTE  (subtipo de PERSONA)
-- VD-01, VD-02 aplicados aquí
-- -------------------------------------------------------
CREATE TABLE cliente (
    id_cliente        INT          NOT NULL AUTO_INCREMENT,
    id_persona        INT          NOT NULL,
    id_ruta           INT          DEFAULT NULL,   -- RF-10: clasificación por ruta
    razon_social      VARCHAR(150) NOT NULL,
    direccion_compuesta VARCHAR(500) NOT NULL,
    credito_autorizado BOOLEAN     NOT NULL DEFAULT FALSE, -- VD-02
    estado_cliente    ENUM('Activo','Inactivo','Suspendido') NOT NULL DEFAULT 'Activo', -- VD-01
    CONSTRAINT pk_cliente    PRIMARY KEY (id_cliente),
    CONSTRAINT uk_cli_persona UNIQUE (id_persona),
    CONSTRAINT fk_cli_persona FOREIGN KEY (id_persona)
        REFERENCES persona(id_persona) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_cli_ruta FOREIGN KEY (id_ruta)
        REFERENCES ruta(id_ruta) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT chk_cli_razon CHECK (LENGTH(TRIM(razon_social)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-04: REPARTIDOR  (subtipo de PERSONA)
-- -------------------------------------------------------
CREATE TABLE repartidor (
    id_repartidor    INT          NOT NULL AUTO_INCREMENT,
    id_persona       INT          NOT NULL,
    licencia         VARCHAR(20)  NOT NULL,
    estado_repartidor ENUM('Activo','Inactivo','Suspendido') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_repartidor   PRIMARY KEY (id_repartidor),
    CONSTRAINT uk_rep_persona  UNIQUE (id_persona),
    CONSTRAINT fk_rep_persona  FOREIGN KEY (id_persona)
        REFERENCES persona(id_persona) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_rep_licencia CHECK (LENGTH(TRIM(licencia)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-06: ASIGNACION_RUTA  (débil-ID respecto a RUTA y REPARTIDOR)
-- -------------------------------------------------------
CREATE TABLE asignacion_ruta (
    id_asignacion INT  NOT NULL AUTO_INCREMENT,
    id_ruta       INT  NOT NULL,
    id_repartidor INT  NOT NULL,
    fecha_inicio  DATE NOT NULL DEFAULT (CURRENT_DATE),
    fecha_fin     DATE DEFAULT NULL,
    observacion   VARCHAR(255) DEFAULT NULL,
    CONSTRAINT pk_asignacion       PRIMARY KEY (id_asignacion),
    CONSTRAINT fk_asig_ruta        FOREIGN KEY (id_ruta)
        REFERENCES ruta(id_ruta) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_asig_repartidor  FOREIGN KEY (id_repartidor)
        REFERENCES repartidor(id_repartidor) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_asig_fechas CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-07: RECORRIDO_RUTA  (débil-ID respecto a RUTA y REPARTIDOR)
-- VD-05 aplicado aquí
-- -------------------------------------------------------
CREATE TABLE recorrido_ruta (
    id_recorrido      INT  NOT NULL AUTO_INCREMENT,
    id_ruta           INT  NOT NULL,
    id_repartidor     INT  NOT NULL,
    fecha             DATE NOT NULL DEFAULT (CURRENT_DATE),  -- VD-03
    turno             ENUM('Mañana','Tarde','Noche') NOT NULL DEFAULT 'Mañana',
    estado_recorrido  ENUM('Pendiente','En curso','Completado','Cancelado') NOT NULL DEFAULT 'Pendiente', -- VD-05
    observacion       VARCHAR(255) DEFAULT NULL,
    CONSTRAINT pk_recorrido       PRIMARY KEY (id_recorrido),
    CONSTRAINT fk_rec_ruta        FOREIGN KEY (id_ruta)
        REFERENCES ruta(id_ruta) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_rec_repartidor  FOREIGN KEY (id_repartidor)
        REFERENCES repartidor(id_repartidor) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-08: PRODUCTO
-- TD-05: tipo_cod_barras aplicado a codigo_barras
-- -------------------------------------------------------
CREATE TABLE producto (
    id_producto      INT          NOT NULL AUTO_INCREMENT,
    nombre_comercial VARCHAR(100) NOT NULL,
    codigo_barras    VARCHAR(50)  NOT NULL,
    categoria        ENUM('Leche','Queso','Natilla','Crema','Cuajada','Yogurt','Otro') NOT NULL,
    estado_producto  ENUM('Activo','Inactivo','Descontinuado') NOT NULL DEFAULT 'Activo',
    CONSTRAINT pk_producto          PRIMARY KEY (id_producto),
    CONSTRAINT uk_prod_cod_barras   UNIQUE (codigo_barras),
    CONSTRAINT chk_prod_nombre      CHECK (LENGTH(TRIM(nombre_comercial)) > 0),
    -- TD-05: tipo_cod_barras — no vacío y sin espacios internos
    CONSTRAINT chk_prod_cod_barras  CHECK (
        LENGTH(TRIM(codigo_barras)) > 0 AND codigo_barras NOT REGEXP ' '
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-09: PRESENTACION  (débil-EX respecto a PRODUCTO)
-- TD-01: tipo_monto aplicado a precio_venta
-- -------------------------------------------------------
CREATE TABLE presentacion (
    id_presentacion     INT           NOT NULL AUTO_INCREMENT,
    id_producto         INT           NOT NULL,
    tamano              VARCHAR(20)   NOT NULL,
    unidad_medida       ENUM('ml','L','g','kg','Unidad') NOT NULL,
    precio_venta        DECIMAL(10,2) NOT NULL,
    descripcion         VARCHAR(255)  DEFAULT NULL,
    estado_presentacion ENUM('Activa','Inactiva') NOT NULL DEFAULT 'Activa',
    CONSTRAINT pk_presentacion  PRIMARY KEY (id_presentacion),
    CONSTRAINT fk_pres_producto FOREIGN KEY (id_producto)
        REFERENCES producto(id_producto) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- TD-01: tipo_monto — valor monetario positivo
    CONSTRAINT chk_pres_precio CHECK (precio_venta > 0 AND precio_venta <= 9999999.99)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-10: LOTE  (débil-EX respecto a PRODUCTO)
-- TD-03: tipo_cantidad aplicado a cantidades
-- -------------------------------------------------------
CREATE TABLE lote (
    id_lote             INT          NOT NULL AUTO_INCREMENT,
    id_producto         INT          NOT NULL,
    numero_lote         VARCHAR(50)  NOT NULL,
    fecha_elaboracion   DATE         NOT NULL,
    fecha_vencimiento   DATE         NOT NULL,
    cantidad_producida  INT          NOT NULL,
    cantidad_disponible INT          NOT NULL,
    estado_lote         ENUM('Disponible','Agotado','Vencido','Retirado') NOT NULL DEFAULT 'Disponible',
    CONSTRAINT pk_lote         PRIMARY KEY (id_lote),
    CONSTRAINT uk_lote_numero  UNIQUE (numero_lote),
    CONSTRAINT fk_lote_producto FOREIGN KEY (id_producto)
        REFERENCES producto(id_producto) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_lote_fechas CHECK (fecha_vencimiento > fecha_elaboracion),
    -- TD-03: tipo_cantidad — entero estrictamente positivo
    CONSTRAINT chk_lote_cant_prod CHECK (cantidad_producida > 0),
    CONSTRAINT chk_lote_cant_disp CHECK (cantidad_disponible >= 0 AND cantidad_disponible <= cantidad_producida)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-11: FACTURA  (supertipo de FACTURA_CONTADO / FACTURA_CREDITO)
-- VD-03, VD-04 aplicados aquí
-- TD-01: tipo_monto aplicado a total
-- -------------------------------------------------------
CREATE TABLE factura (
    id_factura      INT           NOT NULL AUTO_INCREMENT,
    id_cliente      INT           NOT NULL,
    id_repartidor   INT           NOT NULL,
    id_recorrido    INT           NOT NULL,
    numero_factura  VARCHAR(20)   NOT NULL,
    fecha_emision   DATE          NOT NULL DEFAULT (CURRENT_DATE), -- VD-03
    condicion_pago  ENUM('Contado','Crédito') NOT NULL DEFAULT 'Contado', -- VD-04
    estado_factura  ENUM('Emitida','Pagada','Anulada','Pendiente') NOT NULL DEFAULT 'Emitida',
    total           DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT pk_factura       PRIMARY KEY (id_factura),
    CONSTRAINT uk_fact_numero   UNIQUE (numero_factura),
    CONSTRAINT fk_fact_cliente  FOREIGN KEY (id_cliente)
        REFERENCES cliente(id_cliente) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_fact_repartidor FOREIGN KEY (id_repartidor)
        REFERENCES repartidor(id_repartidor) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_fact_recorrido FOREIGN KEY (id_recorrido)
        REFERENCES recorrido_ruta(id_recorrido) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- TD-01: tipo_monto
    CONSTRAINT chk_fact_total   CHECK (total >= 0),
    CONSTRAINT chk_fact_numero  CHECK (numero_factura LIKE 'FAC-%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-12: DETALLE_FACTURA  (débil-ID respecto a FACTURA)
-- TD-01 y TD-03 aplicados aquí
-- -------------------------------------------------------
CREATE TABLE detalle_factura (
    id_detalle      INT           NOT NULL AUTO_INCREMENT,
    id_factura      INT           NOT NULL,
    id_presentacion INT           NOT NULL,
    id_lote         INT           NOT NULL,
    cantidad        INT           NOT NULL,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal        DECIMAL(10,2) NOT NULL,
    observacion     VARCHAR(255)  DEFAULT NULL,
    CONSTRAINT pk_detalle       PRIMARY KEY (id_detalle),
    CONSTRAINT fk_det_factura   FOREIGN KEY (id_factura)
        REFERENCES factura(id_factura) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_det_presenta  FOREIGN KEY (id_presentacion)
        REFERENCES presentacion(id_presentacion) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_det_lote      FOREIGN KEY (id_lote)
        REFERENCES lote(id_lote) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- TD-03: tipo_cantidad
    CONSTRAINT chk_det_cantidad CHECK (cantidad > 0 AND cantidad <= 10000),
    -- TD-01: tipo_monto
    CONSTRAINT chk_det_precio   CHECK (precio_unitario > 0),
    CONSTRAINT chk_det_subtotal CHECK (subtotal > 0),
    -- RNF-01: no cantidades negativas ni precio en cero
    CONSTRAINT chk_det_rnf01    CHECK (cantidad > 0 AND precio_unitario > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-13: FACTURA_CONTADO  (subtipo de FACTURA, especialización disjunta)
-- TD-01 aplicado a monto_recibido y vuelto
-- -------------------------------------------------------
CREATE TABLE factura_contado (
    id_factura     INT           NOT NULL,
    monto_recibido DECIMAL(10,2) NOT NULL,
    vuelto         DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT pk_fact_contado  PRIMARY KEY (id_factura),
    CONSTRAINT fk_fc_factura    FOREIGN KEY (id_factura)
        REFERENCES factura(id_factura) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- TD-01: tipo_monto
    CONSTRAINT chk_fc_monto_rec CHECK (monto_recibido > 0),
    CONSTRAINT chk_fc_vuelto    CHECK (vuelto >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-14: FACTURA_CREDITO  (subtipo de FACTURA, especialización disjunta)
-- TD-01 aplicado a saldo_pendiente y limite_credito_aplicado
-- -------------------------------------------------------
CREATE TABLE factura_credito (
    id_factura              INT           NOT NULL,
    fecha_vencimiento_credito DATE         NOT NULL,
    limite_credito_aplicado DECIMAL(10,2) NOT NULL,
    saldo_pendiente         DECIMAL(10,2) NOT NULL,
    CONSTRAINT pk_fact_credito  PRIMARY KEY (id_factura),
    CONSTRAINT fk_fcc_factura   FOREIGN KEY (id_factura)
        REFERENCES factura(id_factura) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_fcc_saldo    CHECK (saldo_pendiente >= 0),
    CONSTRAINT chk_fcc_limite   CHECK (limite_credito_aplicado > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-15: PAGO
-- TD-01 aplicado a monto
-- -------------------------------------------------------
CREATE TABLE pago (
    id_pago           INT           NOT NULL AUTO_INCREMENT,
    id_factura_credito INT          NOT NULL,
    fecha_pago        DATE          NOT NULL DEFAULT (CURRENT_DATE),
    monto             DECIMAL(10,2) NOT NULL,
    metodo_pago       ENUM('Efectivo','Transferencia','SINPE','Cheque') NOT NULL DEFAULT 'Efectivo',
    numero_comprobante VARCHAR(100) DEFAULT NULL,
    CONSTRAINT pk_pago          PRIMARY KEY (id_pago),
    CONSTRAINT fk_pago_fcc      FOREIGN KEY (id_factura_credito)
        REFERENCES factura_credito(id_factura) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- TD-01: tipo_monto
    CONSTRAINT chk_pago_monto   CHECK (monto > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- E-16: VENTA  (consolidación de factura + detalle para reportes)
-- -------------------------------------------------------
CREATE TABLE venta (
    id_venta    INT  NOT NULL AUTO_INCREMENT,
    id_factura  INT  NOT NULL,
    id_detalle  INT  NOT NULL,
    tipo_venta  ENUM('Contado','Crédito') NOT NULL,
    CONSTRAINT pk_venta       PRIMARY KEY (id_venta),
    CONSTRAINT fk_venta_fact  FOREIGN KEY (id_factura)
        REFERENCES factura(id_factura) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_venta_det   FOREIGN KEY (id_detalle)
        REFERENCES detalle_factura(id_detalle) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- SECCIÓN 3: ÍNDICES
-- IDX-01 Aceleración de reportes por período en FACTURA
-- IDX-02 Detección de lotes próximos a vencer
-- IDX-03 Búsqueda de recorridos por ruta y fecha
-- ============================================================

-- IDX-01: Consultas de ventas por rango de fechas
CREATE INDEX idx_factura_fecha ON factura(fecha_emision);

-- IDX-02: Monitoreo de vencimiento de lotes (RF-04)
CREATE INDEX idx_lote_vencimiento ON lote(fecha_vencimiento, estado_lote);

-- IDX-03: Consultas de recorridos por ruta en una fecha (HU-11)
CREATE INDEX idx_recorrido_ruta_fecha ON recorrido_ruta(id_ruta, fecha);
