-- ============================================================
-- Datos de Prueba
-- Sistema de Facturación – Productos Lácteos María del Carmen
-- ============================================================
USE lacteosdb;
SET NAMES utf8mb4;

-- -------------------------------------------------------
-- Rutas
-- -------------------------------------------------------
INSERT INTO ruta (nombre, zona_geografica, descripcion) VALUES
('Ruta Guanacaste', 'Guanacaste', 'Cubre cantones de Liberia, Nicoya y Santa Cruz'),
('Ruta Limón',      'Limón',      'Cubre cantones de Limón, Pococí y Siquirres');

-- -------------------------------------------------------
-- Personas y Clientes
-- -------------------------------------------------------
INSERT INTO persona (nombre) VALUES
('Carlos Vargas Mora'),       -- 1
('Ana Jiménez Solís'),        -- 2
('Supermercado Hermanos Cruz'),-- 3
('Pulpería La Esquina'),      -- 4
('Distribuidora Norte S.A.'), -- 5
('Minisuper El Palmar'),      -- 6
('Rosa María Esquivel'),      -- 7 (cliente Limón)
('Tienda Don Chico');         -- 8 (cliente Limón)

INSERT INTO cliente (id_persona, id_ruta, razon_social, direccion_compuesta, credito_autorizado) VALUES
(3, 1, 'Supermercado Hermanos Cruz', 'Guanacaste, Liberia, Liberia, 200m norte del parque', TRUE),
(4, 1, 'Pulpería La Esquina',        'Guanacaste, Nicoya, Nicoya, frente al banco', FALSE),
(5, 1, 'Distribuidora Norte S.A.',   'Guanacaste, Santa Cruz, Santa Cruz, zona industrial', TRUE),
(6, 1, 'Minisuper El Palmar',        'Guanacaste, Liberia, Nacascolo, camino principal', FALSE),
(7, 2, 'Rosa María Esquivel',        'Limón, Limón, Limón, barrio Roosevelt', TRUE),
(8, 2, 'Tienda Don Chico',           'Limón, Pococí, Guápiles, avenida 3', FALSE);

-- -------------------------------------------------------
-- Teléfonos de clientes
-- -------------------------------------------------------
INSERT INTO telefono_persona (id_persona, telefono, tipo_telefono) VALUES
(3, '8800-1001', 'Móvil'), (3, '2665-1001', 'Fijo'),
(4, '8800-2002', 'Móvil'),
(5, '8800-3003', 'Móvil'), (5, '8800-3004', 'WhatsApp'),
(6, '8800-4004', 'Móvil'),
(7, '8800-5005', 'Móvil'), (7, '8800-5006', 'WhatsApp'),
(8, '8800-6006', 'Móvil');

-- -------------------------------------------------------
-- Repartidores
-- -------------------------------------------------------
INSERT INTO persona (nombre) VALUES
('Luis Hernández Brenes'),   -- 9
('Marcos Solís Ureña');      -- 10

INSERT INTO repartidor (id_persona, licencia, estado_repartidor) VALUES
(9,  'B3-20001', 'Activo'),
(10, 'B1-30002', 'Activo');

INSERT INTO telefono_persona (id_persona, telefono, tipo_telefono) VALUES
(9,  '8811-9001', 'Móvil'),
(10, '8811-9002', 'Móvil');

-- -------------------------------------------------------
-- Asignaciones de ruta
-- -------------------------------------------------------
INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio) VALUES
(1, 1, '2026-01-01'),
(2, 2, '2026-01-01');

-- -------------------------------------------------------
-- Productos
-- -------------------------------------------------------
INSERT INTO producto (nombre_comercial, codigo_barras, categoria) VALUES
('Cuajada María del Carmen',     '7400001000001', 'Queso'),
('Queso Semiduro',               '7400001000002', 'Queso'),
('Queso Ahumado',                '7400001000003', 'Queso'),
('Queso Molido',                 '7400001000004', 'Queso'),
('Queso Rayado',                 '7400001000005', 'Queso'),
('Natilla',                      '7400001000006', 'Natilla'),
('Leche Agria',                  '7400001000007', 'Leche'),
('Crema',                        '7400001000008', 'Crema');

-- -------------------------------------------------------
-- Presentaciones
-- -------------------------------------------------------
INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta, descripcion) VALUES
-- Cuajada
(1, '500', 'g', 1800.00, 'Empaque en bolsa'),
-- Queso Semiduro
(2, '500', 'g', 2200.00, 'Tapa roja'),
-- Queso Ahumado
(3, '400', 'g', 2500.00, 'Empaque al vacío'),
-- Queso Molido
(4, '1',   'kg', 3800.00, 'Bolsa plástica'),
-- Queso Rayado
(5, '1',   'kg', 4000.00, 'Bolsa con cierre'),
-- Natilla (3 presentaciones)
(6, '1',   'kg', 2000.00, 'Vaso plástico grande'),
(6, '400', 'g',  900.00, 'Vaso plástico mediano'),
(6, '200', 'g',  500.00, 'Vaso plástico pequeño'),
-- Leche Agria
(7, '1',   'L', 1100.00, 'Bolsa sellada'),
-- Crema
(8, '500', 'ml', 1500.00, 'Bolsa sellada');

-- -------------------------------------------------------
-- Lotes
-- -------------------------------------------------------
INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion, fecha_vencimiento, cantidad_producida, cantidad_disponible) VALUES
(1, 'LOT-20260501-001', '2026-05-01', '2026-07-01', 300, 285),
(2, 'LOT-20260501-002', '2026-05-01', '2026-08-01', 200, 190),
(3, 'LOT-20260510-003', '2026-05-10', '2026-08-10', 150, 148),
(4, 'LOT-20260510-004', '2026-05-10', '2026-09-01', 100, 95),
(5, 'LOT-20260510-005', '2026-05-10', '2026-09-01', 100, 92),
(6, 'LOT-20260514-006', '2026-05-14', '2026-06-20', 400, 380),
(6, 'LOT-20260514-007', '2026-05-14', '2026-06-20', 500, 470),
(6, 'LOT-20260514-008', '2026-05-14', '2026-06-20', 600, 590),
(7, 'LOT-20260514-009', '2026-05-14', '2026-06-21', 350, 340),
(8, 'LOT-20260514-010', '2026-05-14', '2026-06-28', 250, 245);

-- -------------------------------------------------------
-- Recorridos
-- -------------------------------------------------------
INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido) VALUES
(1, 1, '2026-06-01', 'Mañana', 'Completado'),
(2, 2, '2026-06-01', 'Mañana', 'Completado'),
(1, 1, '2026-06-08', 'Mañana', 'Completado'),
(2, 2, '2026-06-08', 'Mañana', 'Completado'),
(1, 1, '2026-06-14', 'Mañana', 'En curso');

-- -------------------------------------------------------
-- Facturas y detalles (ejemplos representativos)
-- Las facturas usan los stored procedures para garantizar
-- que los triggers se disparen correctamente.
-- -------------------------------------------------------

-- Factura 1: Contado, Ruta Guanacaste, cliente 1
INSERT INTO factura (id_cliente, id_repartidor, id_recorrido, numero_factura, fecha_emision, condicion_pago, total)
VALUES (1, 1, 1, 'FAC-00001', '2026-06-01', 'Contado', 0);
INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote, cantidad, precio_unitario, subtotal)
VALUES (1, 1, 1, 10, 1800.00, 18000.00),
       (1, 6, 6,  5, 2000.00, 10000.00);
UPDATE factura SET total = 28000.00 WHERE id_factura = 1;
INSERT INTO factura_contado VALUES (1, 30000.00, 2000.00);
UPDATE factura SET estado_factura = 'Pagada' WHERE id_factura = 1;
INSERT INTO venta (id_factura, id_detalle, tipo_venta) VALUES (1, 1, 'Contado'), (1, 2, 'Contado');

-- Factura 2: Crédito, Ruta Guanacaste, cliente 3
INSERT INTO factura (id_cliente, id_repartidor, id_recorrido, numero_factura, fecha_emision, condicion_pago, total)
VALUES (3, 1, 1, 'FAC-00002', '2026-06-01', 'Crédito', 0);
INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote, cantidad, precio_unitario, subtotal)
VALUES (2, 2, 2, 8, 2200.00, 17600.00),
       (2, 7, 7, 12, 900.00, 10800.00);
UPDATE factura SET total = 28400.00 WHERE id_factura = 2;
INSERT INTO factura_credito VALUES (2, '2026-07-01', 50000.00, 28400.00);
UPDATE factura SET estado_factura = 'Pendiente' WHERE id_factura = 2;
INSERT INTO venta (id_factura, id_detalle, tipo_venta) VALUES (2, 3, 'Crédito'), (2, 4, 'Crédito');

-- Abono parcial a la factura 2
INSERT INTO pago (id_factura_credito, fecha_pago, monto, metodo_pago, numero_comprobante)
VALUES (2, '2026-06-10', 15000.00, 'SINPE', 'SINPE-20260610-001');

-- Factura 3: Contado, Ruta Limón, cliente 5
INSERT INTO factura (id_cliente, id_repartidor, id_recorrido, numero_factura, fecha_emision, condicion_pago, total)
VALUES (5, 2, 2, 'FAC-00003', '2026-06-01', 'Contado', 0);
INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote, cantidad, precio_unitario, subtotal)
VALUES (3, 9, 9, 20, 1100.00, 22000.00),
       (3, 10, 10, 10, 1500.00, 15000.00);
UPDATE factura SET total = 37000.00 WHERE id_factura = 3;
INSERT INTO factura_contado VALUES (3, 40000.00, 3000.00);
UPDATE factura SET estado_factura = 'Pagada' WHERE id_factura = 3;
INSERT INTO venta (id_factura, id_detalle, tipo_venta) VALUES (3, 5, 'Contado'), (3, 6, 'Contado');

-- Factura 4: Crédito, Ruta Limón, cliente 5
INSERT INTO factura (id_cliente, id_repartidor, id_recorrido, numero_factura, fecha_emision, condicion_pago, total)
VALUES (5, 2, 4, 'FAC-00004', '2026-06-08', 'Crédito', 0);
INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote, cantidad, precio_unitario, subtotal)
VALUES (4, 4, 4, 5, 3800.00, 19000.00),
       (4, 5, 5, 4, 4000.00, 16000.00);
UPDATE factura SET total = 35000.00 WHERE id_factura = 4;
INSERT INTO factura_credito VALUES (4, '2026-07-08', 50000.00, 35000.00);
UPDATE factura SET estado_factura = 'Pendiente' WHERE id_factura = 4;
INSERT INTO venta (id_factura, id_detalle, tipo_venta) VALUES (4, 7, 'Crédito'), (4, 8, 'Crédito');

-- Actualizar inventario de lotes por las ventas manuales insertadas
UPDATE lote SET cantidad_disponible = 275 WHERE id_lote = 1;
UPDATE lote SET cantidad_disponible = 182 WHERE id_lote = 2;
UPDATE lote SET cantidad_disponible = 375 WHERE id_lote = 6;
UPDATE lote SET cantidad_disponible = 458 WHERE id_lote = 7;
UPDATE lote SET cantidad_disponible = 320 WHERE id_lote = 9;
UPDATE lote SET cantidad_disponible = 235 WHERE id_lote = 10;
UPDATE lote SET cantidad_disponible = 90  WHERE id_lote = 4;
UPDATE lote SET cantidad_disponible = 88  WHERE id_lote = 5;
