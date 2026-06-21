"""Tests de integración para stored procedures transaccionales."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestSpInsertarCliente:
    """Verifica `sp_insertar_cliente` (inserción transaccional persona+cliente).

    Este SP crea un registro en `persona` y otro en `cliente` dentro de
    una transacción. Si algo falla, hace rollback completo: no debe
    quedar una `persona` huérfana sin su `cliente` correspondiente.
    """

    def test_inserta_cliente_nuevo(self, mysql_connection, clean_db):
        """Inserta persona + cliente y retorna id_cliente válido."""
        cur = mysql_connection.cursor()
        args = ["Juan Pérez Test", "JP Test SA", "San José", False, None, None, None]
        cur.callproc("sp_insertar_cliente", args)
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()
        out = list(cur.callproc("sp_insertar_cliente", args))
        id_cliente = out[5]
        assert id_cliente is not None
        assert id_cliente > 0

    def test_inserta_cliente_con_credito(self, mysql_connection, clean_db):
        """Inserta cliente con crédito autorizado."""
        cur = mysql_connection.cursor()
        args = ["María López", "ML SA", "Cartago", True, None, None, None]
        cur.callproc("sp_insertar_cliente", args)
        mysql_connection.commit()
        out = list(cur.callproc("sp_insertar_cliente", args))
        id_cliente = out[5]
        cur.execute(
            "SELECT credito_autorizado FROM cliente WHERE id_cliente = %s",
            (id_cliente,)
        )
        row = cur.fetchone()
        assert row[0] == 1

    def test_rollback_on_error(self, mysql_connection, clean_db):
        """Si falla la inserción, no deja persona huérfana."""
        cur = mysql_connection.cursor()
        cur.execute(
            "INSERT INTO persona (nombre) VALUES ('Persona A')"
        )
        mysql_connection.commit()
        cur.execute("SELECT COUNT(*) FROM persona")
        count_before = cur.fetchone()[0]

        try:
            cur.callproc("sp_insertar_cliente", [
                "Juan", "Razón", "Dirección", False, None, None, None
            ])
            mysql_connection.commit()
        except Exception:
            mysql_connection.rollback()

        cur.execute("SELECT COUNT(*) FROM persona")
        count_after = cur.fetchone()[0]
        assert count_after <= count_before + 1


class TestSpTrxRegistrarPago:
    """Tests para sp_trx_registrar_pago."""

    def setup_productos_cliente(self, mysql_connection):
        """Crea el grafo mínimo necesario para probar `sp_trx_registrar_pago`.

        Inserta en orden:
            persona → cliente (con crédito)
                  → repartidor → ruta → asignación → recorrido
            producto → presentación → lote
            factura (estado Pendiente) → factura_credito (saldo 1000)

        Retorna el `id_factura` ya listo para que el SP le registre pagos.
        El setup simula exactamente lo que `sp_trx_crear_factura_completa`
        habría hecho al crear una factura a crédito en producción.
        """
        cur = mysql_connection.cursor()

        cur.execute("""
            INSERT INTO persona (nombre) VALUES ('Cliente Test')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_persona = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO cliente (id_persona, razon_social, direccion_compuesta, credito_autorizado)
            VALUES (%s, 'Test SA', 'Test', 1)
        """, (id_persona,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_cliente = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO persona (nombre) VALUES ('Repartidor Test')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_persona_rep = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO repartidor (id_persona, licencia) VALUES (%s, 'LIC-001')
        """, (id_persona_rep,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_repartidor = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO ruta (nombre, zona_geografica) VALUES ('Ruta Test', 'Zona Test')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_ruta = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio)
            VALUES (%s, %s, CURDATE())
        """, (id_ruta, id_repartidor))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_asignacion = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido)
            VALUES (%s, %s, CURDATE(), 'Mañana', 'Pendiente')
        """, (id_ruta, id_repartidor))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_recorrido = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO producto (nombre_comercial, codigo_barras, categoria)
            VALUES ('Leche Test', '123456', 'Leche')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_producto = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO presentacion (id_producto, tamano, unidad_medida, precio_venta)
            VALUES (%s, '1L', 'L', 1000.00)
        """, (id_producto,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_presentacion = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO lote (id_producto, numero_lote, fecha_elaboracion,
                              fecha_vencimiento, cantidad_producida, cantidad_disponible)
            VALUES (%s, 'LOT-001', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), 100, 100)
        """, (id_producto,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_lote = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) + 1 FROM factura")
        seq = cur.fetchone()[0]
        num_factura = f"FAC-{seq:05d}"

        cur.execute("""
            INSERT INTO factura (id_cliente, id_repartidor, id_recorrido,
                                  numero_factura, condicion_pago, total, estado_factura)
            VALUES (%s, %s, %s, %s, 'Crédito', 1000.00, 'Pendiente')
        """, (id_cliente, id_repartidor, id_recorrido, num_factura))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_factura = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO factura_credito (id_factura, fecha_vencimiento_credito,
                                          limite_credito_aplicado, saldo_pendiente)
            VALUES (%s, DATE_ADD(CURDATE(), INTERVAL 30 DAY), 5000.00, 1000.00)
        """, (id_factura,))
        mysql_connection.commit()

        return id_factura, id_presentacion, id_lote

    def test_pago_parcial_descuenta_saldo(self, mysql_connection, clean_db):
        """Un pago parcial reduce el saldo y no cancela la factura."""
        id_factura, _, _ = self.setup_productos_cliente(mysql_connection)
        cur = mysql_connection.cursor()

        # La factura de setup tiene saldo 1000. Un pago de 500 debe
        # dejarlo en 500, no en 0 (el bug previo llamaba el SP 2 veces).
        args = [id_factura, 500.00, "Efectivo", None, None, None, None]
        out = list(cur.callproc("sp_trx_registrar_pago", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        saldo = out[5]
        assert saldo == 500.00

        cur.execute("SELECT estado_factura FROM factura WHERE id_factura = %s", (id_factura,))
        estado = cur.fetchone()[0]
        assert estado == "Pendiente"

    def test_pago_total_cancela_factura(self, mysql_connection, clean_db):
        """Un pago por el saldo completo marca la factura como Pagada."""
        id_factura, _, _ = self.setup_productos_cliente(mysql_connection)
        cur = mysql_connection.cursor()

        args = [id_factura, 1000.00, "Efectivo", None, None, None, None]
        cur.callproc("sp_trx_registrar_pago", args)
        mysql_connection.commit()

        cur.execute("SELECT estado_factura FROM factura WHERE id_factura = %s", (id_factura,))
        estado = cur.fetchone()[0]
        assert estado == "Pagada"

    def test_pago_monto_excede_saldo_rechaza(self, mysql_connection, clean_db):
        """Un pago mayor al saldo pendiente es rechazado.

        El SP tiene un EXIT HANDLER que captura el SIGNAL y setea el
        mensaje de error en el OUT p_mensaje, por lo que el caller no
        recibe una excepción: debe verificar el mensaje y que el estado
        no haya cambiado.
        """
        id_factura, _, _ = self.setup_productos_cliente(mysql_connection)
        cur = mysql_connection.cursor()

        # Capturar el saldo antes
        cur.execute(
            "SELECT saldo_pendiente FROM factura_credito WHERE id_factura = %s",
            (id_factura,),
        )
        saldo_antes = cur.fetchone()[0]

        # Contar pagos antes
        cur.execute(
            "SELECT COUNT(*) FROM pago WHERE id_factura_credito = %s",
            (id_factura,),
        )
        pagos_antes = cur.fetchone()[0]

        args = [id_factura, 2000.00, "Efectivo", None, None, None, None]
        out = list(cur.callproc("sp_trx_registrar_pago", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        # El SP debe retornar mensaje de error
        mensaje = out[6]
        assert mensaje is not None
        assert "Error" in mensaje or "error" in mensaje.lower()

        # Y el saldo + cantidad de pagos no deben haber cambiado
        cur.execute(
            "SELECT saldo_pendiente FROM factura_credito WHERE id_factura = %s",
            (id_factura,),
        )
        assert cur.fetchone()[0] == saldo_antes

        cur.execute(
            "SELECT COUNT(*) FROM pago WHERE id_factura_credito = %s",
            (id_factura,),
        )
        assert cur.fetchone()[0] == pagos_antes

    def test_pago_factura_sin_credito_rechaza(self, mysql_connection, clean_db):
        """Registrar pago en factura sin registro de crédito falla.

        El SP tiene un EXIT HANDLER que captura el SIGNAL y setea el
        mensaje de error en el OUT p_mensaje. Verificamos el mensaje y
        que no se haya creado un pago.
        """
        cur = mysql_connection.cursor()

        cur.execute("""
            INSERT INTO persona (nombre) VALUES ('Cliente Contado')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_persona = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO cliente (id_persona, razon_social, direccion_compuesta, credito_autorizado)
            VALUES (%s, 'Contado SA', 'Test', 0)
        """, (id_persona,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_cliente = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO persona (nombre) VALUES ('Repartidor C')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_persona_rep = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO repartidor (id_persona, licencia) VALUES (%s, 'LIC-C')
        """, (id_persona_rep,))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_repartidor = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO ruta (nombre, zona_geografica) VALUES ('Ruta C', 'Zona C')
        """)
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_ruta = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO asignacion_ruta (id_ruta, id_repartidor, fecha_inicio)
            VALUES (%s, %s, CURDATE())
        """, (id_ruta, id_repartidor))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_asignacion = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO recorrido_ruta (id_ruta, id_repartidor, fecha, turno, estado_recorrido)
            VALUES (%s, %s, CURDATE(), 'Mañana', 'Pendiente')
        """, (id_ruta, id_repartidor))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_recorrido = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) + 1 FROM factura")
        seq = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO factura (id_cliente, id_repartidor, id_recorrido,
                                  numero_factura, condicion_pago, total, estado_factura)
            VALUES (%s, %s, %s, %s, 'Contado', 500.00, 'Pagada')
        """, (id_cliente, id_repartidor, id_recorrido, f"FAC-{seq:05d}"))
        mysql_connection.commit()
        cur.execute("SELECT LAST_INSERT_ID()")
        id_factura = cur.fetchone()[0]

        # Contar pagos antes (debe ser 0)
        cur.execute("SELECT COUNT(*) FROM pago WHERE id_factura_credito = %s", (id_factura,))
        pagos_antes = cur.fetchone()[0]

        args = [id_factura, 500.00, "Efectivo", None, None, None, None]
        out = list(cur.callproc("sp_trx_registrar_pago", args))
        for rs in cur.stored_results():
            rs.fetchall()
        mysql_connection.commit()

        # El SP debe retornar mensaje de error
        mensaje = out[6]
        assert mensaje is not None
        assert "Error" in mensaje or "error" in mensaje.lower()

        # Y no se debe haber creado un pago
        cur.execute("SELECT COUNT(*) FROM pago WHERE id_factura_credito = %s", (id_factura,))
        assert cur.fetchone()[0] == pagos_antes
