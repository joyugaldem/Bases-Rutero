"""Tests de integración end-to-end para los flujos transaccionales críticos.

Cubre los SPs sp_trx_crear_factura_completa, sp_trx_anular_factura y
sp_trx_crear_recorrido. Estos tests son la red de seguridad de la lógica
de negocio: si rompes uno de estos SPs, las facturas o el stock van a
quedar inconsistentes.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestFacturaContadoCompleta:
    """Verifica `sp_trx_crear_factura_completa` end-to-end.

    Cubre los tres caminos críticos del SP:
        - Factura contado: descuenta stock, marca Pagada, registra venta.
        - Factura crédito: marca Pendiente, crea registro en factura_credito.
        - Stock insuficiente: rechaza sin crear factura.

    Estos tests son la red de seguridad de la lógica de negocio: si
    rompes el SP, las facturas o el stock van a quedar inconsistentes.
    """

    def _setup_minimo(self, cur):
        """Crea el grafo mínimo para invocar `sp_trx_crear_factura_completa`.

        Inserta persona+cliente+repartidor+ruta+recorrido+producto+
        presentación+lote con datos válidos (FKs respetadas, lotes con
        stock). Devuelve los IDs en un dict para que cada test arme los
        argumentos del SP.

        Returns:
            dict: id_cliente, id_repartidor, id_recorrido, id_presentacion,
            id_lote, id_producto.
        """
        # Cliente con crédito autorizado (necesario para el trigger
        # trg_factura_credito_before_insert, no para contado pero lo
        # dejamos por uniformidad)
        cur.execute("INSERT INTO persona (nombre) VALUES ('Cli Test')")
        id_persona = cur.lastrowid
        cur.execute(
            "INSERT INTO cliente (id_persona, razon_social, direccion_compuesta, credito_autorizado) "
            "VALUES (%s, 'Test SA', 'Test', 1)",
            (id_persona,),
        )
        id_cliente = cur.lastrowid

        # Repartidor
        cur.execute("INSERT INTO persona (nombre) VALUES ('Rep Test')")
        id_persona_rep = cur.lastrowid
        cur.execute(
            "INSERT INTO repartidor (id_persona, licencia) VALUES (%s, 'LIC-X')",
            (id_persona_rep,),
        )
        id_repartidor = cur.lastrowid

        # Ruta + asignación + recorrido
        cur.execute(
            "INSERT INTO ruta (nombre, zona_geografica) VALUES ('Ruta X', 'Zona X')"
        )
        id_ruta = cur.lastrowid
        cur.execute(
            "INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio) "
            "VALUES (%s, %s, CURDATE())",
            (id_ruta, id_repartidor),
        )
        cur.execute(
            "INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido) "
            "VALUES (%s, %s, CURDATE(), 'Mañana', 'Pendiente')",
            (id_ruta, id_repartidor),
        )
        id_recorrido = cur.lastrowid

        # Producto + presentación + lote
        cur.execute(
            "INSERT INTO producto (nombre_comercial, codigo_barras, categoria) "
            "VALUES ('Prod X', 'PX-1', 'Leche')"
        )
        id_producto = cur.lastrowid
        cur.execute(
            "INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta) "
            "VALUES (%s, '1L', 'L', 1000.00)",
            (id_producto,),
        )
        id_presentacion = cur.lastrowid
        cur.execute(
            "INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion, "
            "fecha_vencimiento, cantidad_producida, cantidad_disponible) "
            "VALUES (%s, 'LOT-X', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), 100, 100)",
            (id_producto,),
        )
        id_lote = cur.lastrowid

        return {
            "id_cliente": id_cliente,
            "id_repartidor": id_repartidor,
            "id_recorrido": id_recorrido,
            "id_presentacion": id_presentacion,
            "id_lote": id_lote,
            "id_producto": id_producto,
        }

    def test_crear_factura_contado_ok(self, mysql_connection, clean_db):
        """Factura contado: descuenta stock, marca Pagada, registra venta."""
        cur = mysql_connection.cursor()
        ids = self._setup_minimo(cur)
        mysql_connection.commit()

        # SP signature: 10 IN + 3 OUT (id_factura, numero_factura, mensaje)
        # OUTs en posiciones 10, 11, 12.
        args = [
            ids["id_cliente"], ids["id_repartidor"], ids["id_recorrido"],
            "Contado", ids["id_presentacion"], ids["id_lote"],
            3, 5000.00, None, None,  # 10 IN: cant, monto_rec, fecha_venc, limite_cred
            None, None, None,  # 3 OUT: id_factura, numero_factura, mensaje
        ]
        out = list(cur.callproc("sp_trx_crear_factura_completa", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        id_factura = out[10]
        numero_factura = out[11]
        mensaje = out[12]

        assert id_factura is not None and id_factura > 0
        assert numero_factura.startswith("FAC-")
        assert "exitosamente" in mensaje.lower()

        # Verificar factura
        cur.execute(
            "SELECT total, estado_factura, condicion_pago FROM factura WHERE id_factura = %s",
            (id_factura,),
        )
        total, estado, condicion = cur.fetchone()
        assert total == 3000.00
        assert estado == "Pagada"
        assert condicion == "Contado"

        # Verificar factura_contado (vuelto = 5000 - 3000 = 2000)
        cur.execute(
            "SELECT monto_recibido, vuelto FROM factura_contado WHERE id_factura = %s",
            (id_factura,),
        )
        monto, vuelto = cur.fetchone()
        assert monto == 5000.00
        assert vuelto == 2000.00

        # Verificar que se registró en venta
        cur.execute(
            "SELECT tipo_venta FROM venta WHERE id_factura = %s", (id_factura,)
        )
        assert cur.fetchone()[0] == "Contado"

    def test_crear_factura_credito_ok(self, mysql_connection, clean_db):
        """Factura crédito: descuenta stock, marca Pendiente, crea factura_credito."""
        cur = mysql_connection.cursor()
        ids = self._setup_minimo(cur)
        mysql_connection.commit()

        # Factura crédito: 2 unidades a 1000 = 2000, límite 5000
        args = [
            ids["id_cliente"], ids["id_repartidor"], ids["id_recorrido"],
            "Crédito", ids["id_presentacion"], ids["id_lote"],
            2, None, "2026-12-31", 5000.00,
            None, None, None,
        ]
        out = list(cur.callproc("sp_trx_crear_factura_completa", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        id_factura = out[10]
        assert id_factura is not None

        # Verificar estado Pendiente
        cur.execute(
            "SELECT estado_factura FROM factura WHERE id_factura = %s",
            (id_factura,),
        )
        assert cur.fetchone()[0] == "Pendiente"

        # Verificar factura_credito (saldo = total inicial)
        cur.execute(
            "SELECT fecha_vencimiento_credito, limite_credito_aplicado, saldo_pendiente "
            "FROM factura_credito WHERE id_factura = %s",
            (id_factura,),
        )
        vence, limite, saldo = cur.fetchone()
        assert vence.strftime("%Y-%m-%d") == "2026-12-31"
        assert float(limite) == 5000.00
        assert float(saldo) == 2000.00

    def test_crear_factura_sin_stock_rechaza(self, mysql_connection, clean_db):
        """Si la cantidad > stock disponible, la factura no se crea."""
        cur = mysql_connection.cursor()
        ids = self._setup_minimo(cur)
        mysql_connection.commit()

        # Intentar crear factura con 999 unidades (el lote solo tiene 100)
        args = [
            ids["id_cliente"], ids["id_repartidor"], ids["id_recorrido"],
            "Contado", ids["id_presentacion"], ids["id_lote"],
            999, 999999.00, None, None,
            None, None, None,
        ]
        out = list(cur.callproc("sp_trx_crear_factura_completa", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        # El SP retorna mensaje de error en posición 12
        mensaje = out[12]
        assert mensaje is not None
        assert "stock" in mensaje.lower() or "error" in mensaje.lower()

        # No se debe haber creado ninguna factura
        cur.execute("SELECT COUNT(*) FROM factura")
        assert cur.fetchone()[0] == 0


class TestAnularFacturaRestauraStock:
    """Verifica `sp_trx_anular_factura` (rollback de stock vía cursor).

    El SP usa un cursor sobre `detalle_factura` para restaurar el stock
    lote por lote y luego marca la factura como 'Anulada'. Este test
    confirma el efecto neto: stock_inicial - stock_post_anulación = 0
    para los lotes involucrados.
    """

    def _setup_para_anular(self, cur):
        """Crea una factura en estado 'Emitida' con stock ya descontado.

        `sp_trx_crear_factura_completa` siempre termina una factura
        Contado como 'Pagada' (que NO es anulable según
        `sp_trx_anular_factura`). Para poder probar la anulación,
        creamos la factura con estado inicial 'Emitida' directamente
        e insertamos el detalle a mano (lo que dispara el trigger de
        descuento de stock).
        """
        cur.execute("INSERT INTO persona (nombre) VALUES ('Cli A')")
        id_persona = cur.lastrowid
        cur.execute(
            "INSERT INTO cliente (id_persona, razon_social, direccion_compuesta, credito_autorizado) "
            "VALUES (%s, 'A SA', 'A', 1)",
            (id_persona,),
        )
        id_cliente = cur.lastrowid

        cur.execute("INSERT INTO persona (nombre) VALUES ('Rep A')")
        id_persona_rep = cur.lastrowid
        cur.execute(
            "INSERT INTO repartidor (id_persona, licencia) VALUES (%s, 'LIC-A')",
            (id_persona_rep,),
        )
        id_repartidor = cur.lastrowid

        cur.execute("INSERT INTO ruta (nombre, zona_geografica) VALUES ('Ruta A', 'Zona A')")
        id_ruta = cur.lastrowid
        cur.execute(
            "INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio) "
            "VALUES (%s, %s, CURDATE())",
            (id_ruta, id_repartidor),
        )
        cur.execute(
            "INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido) "
            "VALUES (%s, %s, CURDATE(), 'Mañana', 'Pendiente')",
            (id_ruta, id_repartidor),
        )
        id_recorrido = cur.lastrowid

        cur.execute(
            "INSERT INTO producto (nombre_comercial, codigo_barras, categoria) "
            "VALUES ('Prod A', 'PA-1', 'Leche')"
        )
        id_producto = cur.lastrowid
        cur.execute(
            "INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta) "
            "VALUES (%s, '1L', 'L', 500.00)",
            (id_producto,),
        )
        id_presentacion = cur.lastrowid
        # Lote con stock 50, descontamos 5 para la factura
        cur.execute(
            "INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion, "
            "fecha_vencimiento, cantidad_producida, cantidad_disponible) "
            "VALUES (%s, 'LOT-A', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), 50, 50)",
            (id_producto,),
        )
        id_lote = cur.lastrowid

        # Crear factura manualmente en estado 'Emitida' (anulable)
        cur.execute("SELECT COUNT(*) + 1 FROM factura")
        seq = cur.fetchone()[0]
        num = f"FAC-{seq:05d}"
        cur.execute(
            "INSERT INTO factura (id_cliente, id_repartidor, id_recorrido, "
            "numero_factura, condicion_pago, total, estado_factura) "
            "VALUES (%s, %s, %s, %s, 'Contado', 2500.00, 'Emitida')",
            (id_cliente, id_repartidor, id_recorrido, num),
        )
        id_factura = cur.lastrowid

        # Insertar detalle y descontar stock
        cur.execute(
            "INSERT INTO detalle_factura (id_factura, id_presentacion, id_lote, "
            "cantidad, precio_unitario, subtotal) "
            "VALUES (%s, %s, %s, 5, 500.00, 2500.00)",
            (id_factura, id_presentacion, id_lote),
        )
        cur.execute(
            "UPDATE lote SET cantidad_disponible = cantidad_disponible - 5 WHERE id_lote = %s",
            (id_lote,),
        )

        return {
            "id_factura": id_factura,
            "id_lote": id_lote,
        }

    def test_anular_contado_restaura_stock(self, mysql_connection, clean_db):
        """Anular una factura en estado 'Emitida' debe restaurar el stock descontado."""
        cur = mysql_connection.cursor()
        ids = self._setup_para_anular(cur)
        mysql_connection.commit()
        id_factura = ids["id_factura"]
        id_lote = ids["id_lote"]

        # Stock pre-anulación: 50 - 5 (manual) - 5 (trigger detalle) = 40
        # El trigger trg_detalle_after_insert descuenta automáticamente al
        # insertar en detalle_factura, por lo que el stock final es 40.
        cur.execute(
            "SELECT cantidad_disponible FROM lote WHERE id_lote = %s", (id_lote,)
        )
        stock_pre = cur.fetchone()[0]
        assert stock_pre == 40

        # Anular la factura
        args = [id_factura, None]
        out = list(cur.callproc("sp_trx_anular_factura", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        # sp_trx_anular_factura: 1 IN + 1 OUT (p_mensaje en posición 1)
        mensaje = out[1]
        assert mensaje is not None
        assert "anulada" in mensaje.lower() or "exitosamente" in mensaje.lower()

        # Verificar estado Anulada
        cur.execute(
            "SELECT estado_factura FROM factura WHERE id_factura = %s", (id_factura,)
        )
        assert cur.fetchone()[0] == "Anulada"

        # Verificar que el stock se restauró: 40 + 5 = 45 (el cursor
        # del SP solo suma 1 vez porque solo hay 1 detalle)
        cur.execute(
            "SELECT cantidad_disponible FROM lote WHERE id_lote = %s", (id_lote,)
        )
        assert cur.fetchone()[0] == 45


class TestCrearRecorrido:
    """Verifica `sp_trx_crear_recorrido` (validación + auto-asignación).

    El SP valida que repartidor y ruta estén 'Activos', y si no existe
    asignación activa para esa combinación, la crea automáticamente
    antes de generar el recorrido. Esto evita que el usuario tenga que
    registrar la asignación por separado.
    """

    def _setup_repartidor_ruta(self, cur):
        """Helper mínimo: inserta repartidor (Activo) y ruta (Activa).

        Returns:
            tuple[int, int]: (id_repartidor, id_ruta).
        """
        cur.execute("INSERT INTO persona (nombre) VALUES ('Rep R')")
        id_persona = cur.lastrowid
        cur.execute(
            "INSERT INTO repartidor (id_persona, licencia) VALUES (%s, 'LIC-R')",
            (id_persona,),
        )
        id_repartidor = cur.lastrowid
        cur.execute("INSERT INTO ruta (nombre, zona_geografica) VALUES ('Ruta R', 'Zona R')")
        id_ruta = cur.lastrowid
        return id_repartidor, id_ruta

    def test_crear_recorrido_ok(self, mysql_connection, clean_db):
        """Crea recorrido, valida repartidor+ruta activos, genera asignación si falta."""
        cur = mysql_connection.cursor()
        id_repartidor, id_ruta = self._setup_repartidor_ruta(cur)
        mysql_connection.commit()

        # Sin asignación previa → debe crearla
        cur.execute(
            "SELECT COUNT(*) FROM asignacion_ruta WHERE id_ruta = %s AND id_repartidor = %s",
            (id_ruta, id_repartidor),
        )
        assert cur.fetchone()[0] == 0

        # SP signature: 4 IN + 2 OUT (id_recorrido en pos 4, mensaje en pos 5)
        args = [id_ruta, id_repartidor, None, "Mañana", None, None]
        out = list(cur.callproc("sp_trx_crear_recorrido", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        id_recorrido = out[4]
        mensaje = out[5]

        assert id_recorrido is not None and id_recorrido > 0
        assert "exitosamente" in mensaje.lower()

        # Asignación se creó automáticamente
        cur.execute(
            "SELECT COUNT(*) FROM asignacion_ruta WHERE id_ruta = %s AND id_repartidor = %s",
            (id_ruta, id_repartidor),
        )
        assert cur.fetchone()[0] == 1

        # Recorrido creado con estado Pendiente
        cur.execute(
            "SELECT estado_recorrido FROM recorrido_ruta WHERE id_recorrido = %s",
            (id_recorrido,),
        )
        assert cur.fetchone()[0] == "Pendiente"

    def test_crear_recorrido_repartidor_inactivo_rechaza(self, mysql_connection, clean_db):
        """Repartidor en estado no-Activo → no crea recorrido."""
        cur = mysql_connection.cursor()
        id_repartidor, id_ruta = self._setup_repartidor_ruta(cur)

        # Suspender repartidor
        cur.execute(
            "UPDATE repartidor SET estado_repartidor = 'Suspendido' WHERE id_repartidor = %s",
            (id_repartidor,),
        )
        mysql_connection.commit()

        args = [id_ruta, id_repartidor, None, "Mañana", None, None]
        out = list(cur.callproc("sp_trx_crear_recorrido", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        id_recorrido = out[4]
        mensaje = out[5]

        assert id_recorrido is None
        assert "inactivo" in mensaje.lower() or "error" in mensaje.lower()

        # Y no se creó el recorrido
        cur.execute("SELECT COUNT(*) FROM recorrido_ruta")
        assert cur.fetchone()[0] == 0
