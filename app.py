"""
Aplicación principal Flask – Sistema de Facturación
Productos Lácteos María del Carmen
Módulos: Productos, Clientes, Rutas/Repartidores, Facturación
"""

from flask import Flask, render_template, redirect, url_for, request, flash
import os
import config
from db import get_db, close_db, call_proc, call_proc_out, query

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(close_db)

# ============================================================
# INICIO
# ============================================================

@app.route("/")
def index():
    """Página de inicio con resumen del sistema."""
    try:
        stats = {
            "productos":   query("SELECT COUNT(*) AS n FROM producto WHERE estado_producto='Activo'", fetchone=True)["n"],
            "clientes":    query("SELECT COUNT(*) AS n FROM cliente WHERE estado_cliente='Activo'", fetchone=True)["n"],
            "rutas":       query("SELECT COUNT(*) AS n FROM ruta WHERE estado_ruta='Activa'", fetchone=True)["n"],
            "pendientes":  query("SELECT COUNT(*) AS n FROM vista_facturas_pendientes", fetchone=True)["n"],
        }
    except Exception:
        stats = {"productos": 0, "clientes": 0, "rutas": 0, "pendientes": 0}
    return render_template("index.html", stats=stats)


# ============================================================
# MÓDULO: PRODUCTOS
# ============================================================

@app.route("/productos")
def productos_lista():
    rows = call_proc("sp_consultar_productos", [None])
    return render_template("productos/index.html", productos=rows[0] if rows else [])


@app.route("/productos/nuevo", methods=["GET", "POST"])
def productos_nuevo():
    if request.method == "POST":
        nombre  = request.form["nombre"]
        barras  = request.form["codigo_barras"]
        categ   = request.form["categoria"]
        try:
            _, out = call_proc_out("sp_insertar_producto", [nombre, barras, categ, None])
            flash("Producto registrado correctamente.", "success")
            return redirect(url_for("producto_detalle", id=out[3]))
        except Exception as e:
            flash(f"Error al registrar producto: {e}", "danger")
    categorias = ["Leche","Queso","Natilla","Crema","Cuajada","Yogurt","Otro"]
    return render_template("productos/form.html", producto=None, categorias=categorias)


@app.route("/productos/<int:id>")
def producto_detalle(id):
    prod = call_proc("sp_consultar_productos", [id])
    if not prod or not prod[0]:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("productos_lista"))
    presentaciones = call_proc("sp_consultar_presentaciones", [id])
    lotes          = call_proc("sp_consultar_lotes", [id])
    return render_template("productos/detail.html",
                           producto=prod[0][0],
                           presentaciones=presentaciones[0] if presentaciones else [],
                           lotes=lotes[0] if lotes else [])


@app.route("/productos/<int:id>/editar", methods=["GET", "POST"])
def producto_editar(id):
    if request.method == "POST":
        try:
            call_proc("sp_modificar_producto", [
                id,
                request.form["nombre"],
                request.form["codigo_barras"],
                request.form["categoria"],
                request.form["estado"]
            ])
            flash("Producto actualizado.", "success")
            return redirect(url_for("producto_detalle", id=id))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    prod = call_proc("sp_consultar_productos", [id])
    categorias = ["Leche","Queso","Natilla","Crema","Cuajada","Yogurt","Otro"]
    estados    = ["Activo","Inactivo","Descontinuado"]
    return render_template("productos/form.html",
                           producto=prod[0][0] if prod and prod[0] else None,
                           categorias=categorias, estados=estados)


@app.route("/productos/<int:id>/eliminar", methods=["POST"])
def producto_eliminar(id):
    try:
        call_proc("sp_eliminar_producto", [id])
        flash("Producto eliminado/descontinuado.", "info")
    except Exception as e:
        flash(f"Error al eliminar: {e}", "danger")
    return redirect(url_for("productos_lista"))


# --- Presentaciones ---

@app.route("/presentaciones/nueva/<int:id_producto>", methods=["GET", "POST"])
def presentacion_nueva(id_producto):
    if request.method == "POST":
        try:
            call_proc_out("sp_insertar_presentacion", [
                id_producto,
                request.form["tamano"],
                request.form["unidad_medida"],
                float(request.form["precio_venta"]),
                request.form.get("descripcion") or None,
                None
            ])
            flash("Presentación registrada.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("producto_detalle", id=id_producto))
    prod = call_proc("sp_consultar_productos", [id_producto])
    unidades = ["ml","L","g","kg","Unidad"]
    return render_template("productos/form_presentacion.html",
                           producto=prod[0][0] if prod and prod[0] else None,
                           unidades=unidades)


# --- Lotes ---

@app.route("/lotes/nuevo/<int:id_producto>", methods=["GET", "POST"])
def lote_nuevo(id_producto):
    if request.method == "POST":
        try:
            call_proc_out("sp_insertar_lote", [
                id_producto,
                request.form["numero_lote"],
                request.form["fecha_elaboracion"],
                request.form["fecha_vencimiento"],
                int(request.form["cantidad"]),
                None
            ])
            flash("Lote registrado.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("producto_detalle", id=id_producto))
    prod = call_proc("sp_consultar_productos", [id_producto])
    return render_template("productos/form_lote.html",
                           producto=prod[0][0] if prod and prod[0] else None)


# ============================================================
# MÓDULO: CLIENTES
# ============================================================

@app.route("/clientes")
def clientes_lista():
    rows = call_proc("sp_consultar_clientes", [None])
    return render_template("clientes/index.html", clientes=rows[0] if rows else [])


@app.route("/clientes/nuevo", methods=["GET", "POST"])
def cliente_nuevo():
    if request.method == "POST":
        try:
            _, out = call_proc_out("sp_insertar_cliente", [
                request.form["nombre"],
                request.form["razon_social"],
                request.form["direccion"],
                request.form.get("credito") == "1",
                request.form.get("id_ruta") or None,
                None
            ])
            # Registrar teléfonos
            tel = request.form.get("telefono", "").strip()
            if tel:
                call_proc("sp_insertar_telefono", [
                    query("SELECT id_persona FROM cliente WHERE id_cliente=%s",
                          [out[5]], fetchone=True)["id_persona"],
                    tel,
                    request.form.get("tipo_telefono", "Móvil")
                ])
            flash("Cliente registrado correctamente.", "success")
            return redirect(url_for("clientes_lista"))
        except Exception as e:
            flash(f"Error al registrar cliente: {e}", "danger")
    rutas = call_proc("sp_consultar_rutas", [None])
    return render_template("clientes/form.html",
                           cliente=None,
                           rutas=rutas[0] if rutas else [])


@app.route("/clientes/<int:id>")
def cliente_detalle(id):
    rows = call_proc("sp_consultar_clientes", [id])
    if not rows or not rows[0]:
        flash("Cliente no encontrado.", "warning")
        return redirect(url_for("clientes_lista"))
    cliente = rows[0][0]
    # Obtener persona para teléfonos
    persona = query("SELECT id_persona FROM cliente WHERE id_cliente=%s", [id], fetchone=True)
    telefonos = call_proc("sp_consultar_telefonos", [persona["id_persona"]]) if persona else []
    facturas  = call_proc("sp_consultar_facturas", [id, None, None])
    return render_template("clientes/detail.html",
                           cliente=cliente,
                           telefonos=telefonos[0] if telefonos else [],
                           facturas=facturas[0] if facturas else [])


@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
def cliente_editar(id):
    if request.method == "POST":
        try:
            call_proc("sp_modificar_cliente", [
                id,
                request.form["nombre"],
                request.form["razon_social"],
                request.form["direccion"],
                request.form.get("credito") == "1",
                request.form.get("id_ruta") or None,
                request.form["estado"]
            ])
            flash("Cliente actualizado.", "success")
            return redirect(url_for("cliente_detalle", id=id))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    rows  = call_proc("sp_consultar_clientes", [id])
    rutas = call_proc("sp_consultar_rutas", [None])
    estados = ["Activo","Inactivo","Suspendido"]
    return render_template("clientes/form.html",
                           cliente=rows[0][0] if rows and rows[0] else None,
                           rutas=rutas[0] if rutas else [],
                           estados=estados)


@app.route("/clientes/<int:id>/eliminar", methods=["POST"])
def cliente_eliminar(id):
    try:
        call_proc("sp_eliminar_cliente", [id])
        flash("Cliente desactivado.", "info")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("clientes_lista"))


# ============================================================
# MÓDULO: RUTAS Y REPARTIDORES
# ============================================================

@app.route("/rutas")
def rutas_lista():
    rutas = call_proc("sp_consultar_rutas", [None])
    return render_template("rutas/index.html", rutas=rutas[0] if rutas else [])


@app.route("/rutas/nueva", methods=["GET", "POST"])
def ruta_nueva():
    if request.method == "POST":
        try:
            call_proc_out("sp_insertar_ruta", [
                request.form["nombre"],
                request.form["zona_geografica"],
                request.form.get("descripcion") or None,
                None
            ])
            flash("Ruta registrada.", "success")
            return redirect(url_for("rutas_lista"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("rutas/form.html", ruta=None)


@app.route("/rutas/<int:id>")
def ruta_detalle(id):
    rutas = call_proc("sp_consultar_rutas", [id])
    if not rutas or not rutas[0]:
        flash("Ruta no encontrada.", "warning")
        return redirect(url_for("rutas_lista"))
    asignaciones = call_proc("sp_consultar_asignaciones", [id, None])
    recorridos   = call_proc("sp_consultar_recorridos", [id, None])
    return render_template("rutas/detail.html",
                           ruta=rutas[0][0],
                           asignaciones=asignaciones[0] if asignaciones else [],
                           recorridos=recorridos[0] if recorridos else [])


@app.route("/rutas/<int:id>/editar", methods=["GET", "POST"])
def ruta_editar(id):
    if request.method == "POST":
        try:
            call_proc("sp_modificar_ruta", [
                id,
                request.form["nombre"],
                request.form["zona_geografica"],
                request.form.get("descripcion") or None,
                request.form["estado"]
            ])
            flash("Ruta actualizada.", "success")
            return redirect(url_for("ruta_detalle", id=id))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    rutas  = call_proc("sp_consultar_rutas", [id])
    estados = ["Activa","Inactiva","Suspendida"]
    return render_template("rutas/form.html",
                           ruta=rutas[0][0] if rutas and rutas[0] else None,
                           estados=estados)


# --- Recorridos ---

@app.route("/recorridos/nuevo", methods=["GET", "POST"])
def recorrido_nuevo():
    if request.method == "POST":
        try:
            _, out = call_proc_out("sp_trx_crear_recorrido", [
                int(request.form["id_ruta"]),
                int(request.form["id_repartidor"]),
                request.form["fecha"] or None,
                request.form["turno"],
                None,
                None
            ])
            flash(out[5], "success")
            return redirect(url_for("ruta_detalle", id=request.form["id_ruta"]))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    rutas       = call_proc("sp_consultar_rutas", [None])
    repartidores = call_proc("sp_consultar_repartidores", [None])
    return render_template("rutas/form_recorrido.html",
                           rutas=rutas[0] if rutas else [],
                           repartidores=repartidores[0] if repartidores else [])


# --- Repartidores ---

@app.route("/repartidores")
def repartidores_lista():
    rows = call_proc("sp_consultar_repartidores", [None])
    return render_template("repartidores/index.html", repartidores=rows[0] if rows else [])


@app.route("/repartidores/nuevo", methods=["GET", "POST"])
def repartidor_nuevo():
    if request.method == "POST":
        try:
            call_proc_out("sp_insertar_repartidor", [
                request.form["nombre"],
                request.form["licencia"],
                None
            ])
            flash("Repartidor registrado.", "success")
            return redirect(url_for("repartidores_lista"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("repartidores/form.html", repartidor=None)


@app.route("/repartidores/<int:id>/editar", methods=["GET", "POST"])
def repartidor_editar(id):
    if request.method == "POST":
        try:
            call_proc("sp_modificar_repartidor", [
                id,
                request.form["nombre"],
                request.form["licencia"],
                request.form["estado"]
            ])
            flash("Repartidor actualizado.", "success")
            return redirect(url_for("repartidores_lista"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    rows   = call_proc("sp_consultar_repartidores", [id])
    estados = ["Activo","Inactivo","Suspendido"]
    return render_template("repartidores/form.html",
                           repartidor=rows[0][0] if rows and rows[0] else None,
                           estados=estados)


# ============================================================
# MÓDULO: FACTURACIÓN
# ============================================================

@app.route("/facturacion")
def facturacion_lista():
    fecha_desde = request.args.get("desde") or None
    fecha_hasta = request.args.get("hasta") or None
    id_cliente  = request.args.get("cliente") or None
    rows = call_proc("sp_consultar_facturas", [id_cliente, fecha_desde, fecha_hasta])
    clientes = call_proc("sp_consultar_clientes", [None])
    return render_template("facturacion/index.html",
                           facturas=rows[0] if rows else [],
                           clientes=clientes[0] if clientes else [],
                           filtros={"desde": fecha_desde, "hasta": fecha_hasta, "cliente": id_cliente})


@app.route("/facturacion/nueva", methods=["GET", "POST"])
def factura_nueva():
    if request.method == "POST":
        try:
            id_cliente    = int(request.form["id_cliente"])
            id_repartidor = int(request.form["id_repartidor"])
            id_recorrido  = int(request.form["id_recorrido"])
            condicion     = request.form["condicion_pago"]
            id_presentacion = int(request.form["id_presentacion"])
            id_lote       = int(request.form["id_lote"])
            cantidad      = int(request.form["cantidad"])
            monto_rec     = float(request.form.get("monto_recibido") or 0)
            fecha_venc    = request.form.get("fecha_vencimiento_credito") or None
            limite_cred   = float(request.form.get("limite_credito") or 0)

            _, out = call_proc_out("sp_trx_crear_factura_completa", [
                id_cliente, id_repartidor, id_recorrido, condicion,
                id_presentacion, id_lote, cantidad,
                monto_rec if condicion == "Contado" else None,
                fecha_venc if condicion == "Crédito" else None,
                limite_cred if condicion == "Crédito" else None,
                None, None, None
            ])
            msg = out[12]
            if "exitosamente" in (msg or ""):
                flash(msg, "success")
                return redirect(url_for("factura_detalle", id=out[10]))
            else:
                flash(msg or "Error desconocido.", "danger")
        except Exception as e:
            flash(f"Error al crear factura: {e}", "danger")

    clientes     = call_proc("sp_consultar_clientes", [None])
    repartidores = call_proc("sp_consultar_repartidores", [None])
    recorridos   = call_proc("sp_consultar_recorridos", [None, None])
    catalogo     = query("SELECT * FROM vista_catalogo_productos")
    return render_template("facturacion/nueva.html",
                           clientes=clientes[0] if clientes else [],
                           repartidores=repartidores[0] if repartidores else [],
                           recorridos=recorridos[0] if recorridos else [],
                           catalogo=catalogo)


@app.route("/facturacion/<int:id>")
def factura_detalle(id):
    rows     = call_proc("sp_consultar_facturas", [None, None, None])
    factura  = next((f for f in (rows[0] if rows else []) if f["id_factura"] == id), None)
    if not factura:
        flash("Factura no encontrada.", "warning")
        return redirect(url_for("facturacion_lista"))
    detalles = call_proc("sp_consultar_detalles", [id])
    pagos    = call_proc("sp_consultar_pagos", [id])
    credito  = call_proc("sp_consultar_factura_credito", [id])
    return render_template("facturacion/detalle.html",
                           factura=factura,
                           detalles=detalles[0] if detalles else [],
                           pagos=pagos[0] if pagos else [],
                           credito=credito[0][0] if credito and credito[0] else None)


@app.route("/facturacion/<int:id>/pagar", methods=["GET", "POST"])
def factura_pagar(id):
    if request.method == "POST":
        try:
            _, out = call_proc_out("sp_trx_registrar_pago", [
                id,
                float(request.form["monto"]),
                request.form["metodo_pago"],
                request.form.get("comprobante") or None,
                None, None, None
            ])
            flash(out[6], "success" if "exitosamente" in (out[6] or "") else "info")
        except Exception as e:
            flash(f"Error al registrar pago: {e}", "danger")
        return redirect(url_for("factura_detalle", id=id))
    credito = call_proc("sp_consultar_factura_credito", [id])
    return render_template("facturacion/pago.html",
                           id_factura=id,
                           credito=credito[0][0] if credito and credito[0] else None)


@app.route("/facturacion/<int:id>/anular", methods=["POST"])
def factura_anular(id):
    try:
        _, out = call_proc_out("sp_trx_anular_factura", [id, None])
        flash(out[1], "info")
    except Exception as e:
        flash(f"Error al anular: {e}", "danger")
    return redirect(url_for("factura_detalle", id=id))


# ============================================================
# MÓDULO: REPORTES
# ============================================================

@app.route("/reportes/ventas-por-ruta")
def rpt_ventas_ruta():
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    rows  = call_proc("sp_rpt_ventas_por_ruta", [desde, hasta])
    return render_template("reportes/ventas_ruta.html",
                           datos=rows[0] if rows else [],
                           filtros={"desde": desde, "hasta": hasta})


@app.route("/reportes/creditos")
def rpt_creditos():
    rows = call_proc("sp_cur_resumen_creditos", [])
    return render_template("reportes/creditos.html",
                           datos=rows[0] if rows else [])


@app.route("/reportes/productos-por-vencer")
def rpt_productos_vencer():
    dias = int(request.args.get("dias", 30))
    rows = call_proc("sp_rpt_productos_proximos_vencer", [dias])
    return render_template("reportes/productos_vencer.html",
                           datos=rows[0] if rows else [], dias=dias)


@app.route("/reportes/top-productos")
def rpt_top_productos():
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    rows  = call_proc("sp_rpt_top_productos_vendidos", [desde, hasta, None])
    return render_template("reportes/top_productos.html",
                           datos=rows[0] if rows else [],
                           filtros={"desde": desde, "hasta": hasta})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
