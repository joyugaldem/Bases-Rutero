CATEGORIAS_PRODUCTO = ["Leche", "Queso", "Natilla", "Crema", "Cuajada", "Yogurt", "Otro"]
UNIDADES_MEDIDA = ["ml", "L", "g", "kg", "Unidad"]
ESTADOS_PRODUCTO = ["Activo", "Inactivo", "Descontinuado"]
ESTADOS_CLIENTE = ["Activo", "Inactivo", "Suspendido"]
ESTADOS_RUTA = ["Activa", "Inactiva", "Suspendida"]
ESTADOS_REPARTIDOR = ["Activo", "Inactivo", "Suspendido"]
METODOS_PAGO = ["Efectivo", "Transferencia", "SINPE", "Cheque"]
CONDICIONES_PAGO = ["Contado", "Crédito"]
TURNOS = ["Mañana", "Tarde", "Noche"]
TIPOS_TELEFONO = ["Móvil", "Casa", "Trabajo", "Otro"]

SUCCESS_PREFIX = "OK:"

SP_OUT = {
    "sp_insertar_producto":          ["id_producto"],
    "sp_insertar_presentacion":      ["id_presentacion"],
    "sp_insertar_lote":              ["id_lote"],
    "sp_insertar_cliente":           ["id_cliente", "id_persona"],
    "sp_insertar_ruta":              ["id_ruta"],
    "sp_insertar_repartidor":        ["id_repartidor"],
    "sp_trx_crear_recorrido":        ["id_recorrido", "mensaje"],
    "sp_trx_crear_factura_completa": ["id_factura", "numero_factura", "mensaje"],
    "sp_trx_registrar_pago":         ["id_pago", "saldo_restante", "mensaje"],
    "sp_trx_anular_factura":         ["mensaje"],
    "sp_trx_registrar_producto_completo": ["id_producto", "id_presentacion", "id_lote", "mensaje"],
}
