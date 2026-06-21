"""
Aplicación principal Flask – Sistema de Facturación
Productos Lácteos María del Carmen
Módulos: Productos, Clientes, Rutas/Repartidores, Facturación
"""

import functools
import logging
import os
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.exceptions import BadRequestKeyError
import config
from db import get_db, close_db, call_proc, call_proc_dict, call_proc_named, query
import constants

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(close_db)

# ============================================================
# CSRF Protection
# ============================================================
# Flask-WTF valida automáticamente un token csrf_token en todas las
# peticiones POST/PUT/DELETE/PATCH. Los templates deben incluir
# {{ csrf_token() }} dentro de cada <form method="post">.
# También acepta el header X-CSRFToken (útil para AJAX).
csrf = CSRFProtect(app)


# ============================================================
# Logging
# ============================================================
def _configure_logging():
    """Configura logging estructurado: archivo rotativo + consola.

    En producción rota el archivo logs/app.log (10 MB máx, 5 backups).
    En desarrollo va solo a stderr.
    """
    if not config.FLASK_DEBUG:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO if not config.FLASK_DEBUG else logging.DEBUG)
    app.logger.info("App iniciada (debug=%s)", config.FLASK_DEBUG)


_configure_logging()


# ============================================================
# Security headers
# ============================================================
@app.after_request
def add_security_headers(response):
    """Añade headers de seguridad a todas las respuestas HTTP."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


@app.context_processor
def inject_globals():
    """Inyecta constantes y csrf_token() a todos los templates.

    csrf_token() se inyecta explícitamente para que esté disponible
    sin tener que importar flask_wtf en cada template.
    """
    return {"constants": constants, "csrf_token": generate_csrf}


def form_get(key, cast=str, default=None):
    """Lee y castea un valor de request.form de forma segura.

    - Devuelve `default` si el campo está vacío o ausente.
    - Lanza `ValueError` con mensaje descriptivo si el cast falla.
    - Hace strip() antes de castear (tolera espacios accidentales).
    """
    raw = request.form.get(key, "")
    if raw is None:
        raw = ""
    val = raw.strip()
    if not val:
        return default
    try:
        return cast(val)
    except (ValueError, TypeError):
        raise ValueError(f"campo '{key}' con valor inválido: {val!r}")


def handle_form_errors(view):
    """Decorator que captura errores de parseo de formulario.

    Convierte ValueError (de form_get) y BadRequestKeyError (de
    request.form[]) en un flash y un redirect a la página anterior
    (o al index) en lugar de un 500.
    """
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValueError as e:
            flash(f"Error en formulario: {e}", "danger")
            return redirect(request.referrer or url_for("index"))
        except BadRequestKeyError as e:
            key = e.args[0] if e.args else "desconocido"
            flash(f"Campo requerido ausente: '{key}'", "danger")
            return redirect(request.referrer or url_for("index"))
    return wrapper


def flash_out(out, fallback_danger="Error desconocido."):
    """Flashea el mensaje OUT de un SP. Reconoce prefijo OK: para éxito."""
    msg = (out.get("mensaje") if isinstance(out, dict) else None) or fallback_danger
    if isinstance(msg, str) and msg.startswith(constants.SUCCESS_PREFIX):
        flash(msg[len(constants.SUCCESS_PREFIX):], "success")
    else:
        flash(msg, "danger")


def paginate(items, per_page=20):
    """Pagina una lista en memoria y retorna (page_items, pager_info).

    `pager_info` es un dict listo para pasar al template:
        {"page": int, "pages": int, "total": int, "has_prev": bool, "has_next": bool}

    Lee `page` de `request.args` (default 1). Lanza ValueError si page
    no es entero positivo (cae en handle_form_errors).
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        raise ValueError(f"parámetro 'page' inválido: {request.args.get('page')!r}")

    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)  # ceil(total/per_page)
    page = min(page, pages)  # clamp al máximo
    start = (page - 1) * per_page
    end = start + per_page

    return items[start:end], {
        "page": page,
        "pages": pages,
        "total": total,
        "per_page": per_page,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_page": page - 1,
        "next_page": page + 1,
    }

# ============================================================
# INICIO
# ============================================================

@app.route("/")
def index():
    """Página de inicio con resumen del sistema.

    Muestra cuatro contadores: productos activos, clientes activos,
    rutas activas y facturas pendientes de pago (crédito con saldo).

    Si la BD no responde, no rompe: captura la excepción y muestra
    ceros en lugar de un 500, para que la app siga siendo navegable
    aunque el backend de datos esté caído.

    Template:
        index.html
    """
    empty = {"productos": 0, "clientes": 0, "rutas": 0, "pendientes": 0}
    try:
        row = query("""
            SELECT
              (SELECT COUNT(*) FROM producto  WHERE estado_producto='Activo') AS productos,
              (SELECT COUNT(*) FROM cliente   WHERE estado_cliente='Activo')  AS clientes,
              (SELECT COUNT(*) FROM ruta      WHERE estado_ruta='Activa')     AS rutas,
              (SELECT COUNT(*) FROM vista_facturas_pendientes)                AS pendientes
        """, fetchone=True, default=empty)
        stats = row if row else empty
    except Exception:
        stats = empty
    return render_template("index.html", stats=stats)


# ============================================================
# MÓDULO: PRODUCTOS
# ============================================================

@app.route("/productos")
def productos_lista():
    """Lista los productos con búsqueda y paginación server-side.

    Query params:
        q: texto a buscar en nombre_comercial, codigo_barras o categoria
           (case-insensitive, match parcial).
        page: número de página (default 1, ver paginate()).

    El filtrado se hace en Python (no en SQL) porque la lista ya
    viene del SP `sp_consultar_productos(NULL)`; para conjuntos
    grandes se recomienda mover el filtro a SQL.

    SPs:
        sp_consultar_productos(NULL)

    Template:
        productos/index.html
    """
    rows = call_proc("sp_consultar_productos", [None])
    all_items = rows[0] if rows else []
    q = (request.args.get("q") or "").strip().lower()
    if q:
        all_items = [p for p in all_items
                     if q in (p.get("nombre_comercial") or "").lower()
                     or q in (p.get("codigo_barras") or "").lower()
                     or q in (p.get("categoria") or "").lower()]
    items, pager = paginate(all_items, per_page=20)
    return render_template("productos/index.html",
                           productos=items, pager=pager, q=q)


@app.route("/productos/nuevo", methods=["GET", "POST"])
def productos_nuevo():
    """Crea un producto (GET muestra form, POST persiste).

    Form (POST):
        nombre: nombre comercial (obligatorio, no vacío).
        codigo_barras: EAN-13 u otro (validado en SQL: único y sin
                       espacios).
        categoria: una de constants.CATEGORIAS_PRODUCTO.

    SPs:
        sp_insertar_producto → devuelve id_producto (OUT).

    Template:
        productos/form.html (con categorías en el dropdown).

    Efectos: flash + redirect a /productos/<id> tras éxito.
    """
    if request.method == "POST":
        try:
            _, out = call_proc_named(
                "sp_insertar_producto",
                [request.form["nombre"], request.form["codigo_barras"], request.form["categoria"]],
                constants.SP_OUT["sp_insertar_producto"],
            )
            flash("Producto registrado correctamente.", "success")
            return redirect(url_for("producto_detalle", id=out["id_producto"]))
        except Exception as e:
            flash(f"Error al registrar producto: {e}", "danger")
    categorias = constants.CATEGORIAS_PRODUCTO
    return render_template("productos/form.html", producto=None, categorias=categorias)


@app.route("/productos/<int:id>")
def producto_detalle(id):
    """Detalle de un producto con sus presentaciones y lotes.

    Args:
        id: id_producto (path int).

    SPs:
        sp_consultar_productos(id)
        sp_consultar_presentaciones(id_producto)
        sp_consultar_lotes(id_producto)

    Template:
        productos/detail.html (muestra stock por lote, presentaciones
        activas, y permite agregar nueva presentación/lote).

    Efectos: si el producto no existe, flash warning + redirect a
    /productos.
    """
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
    """Edita nombre, código de barras, categoría y estado.

    Form (POST):
        nombre, codigo_barras, categoria, estado (Activo/Inactivo/
        Descontinuado).

    SPs:
        sp_modificar_producto (5 IN).
        sp_consultar_productos(id) — solo para prellenar el form en GET.

    Template:
        productos/form.html (con producto en contexto + estados).

    Efectos: flash + redirect a /productos/<id> tras éxito.
    """
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
    categorias = constants.CATEGORIAS_PRODUCTO
    estados    = constants.ESTADOS_PRODUCTO
    return render_template("productos/form.html",
                           producto=prod[0][0] if prod and prod[0] else None,
                           categorias=categorias, estados=estados)


@app.route("/productos/<int:id>/eliminar", methods=["POST"])
def producto_eliminar(id):
    """Elimina (o descontinúa) un producto.

    Solo POST. El form se muestra en un modal de confirmación
    (ver macro `confirm_delete`). CSRF validado por Flask-WTF.

    SPs:
        sp_eliminar_producto — si tiene ventas, hace borrado lógico
        (cambia estado a 'Descontinuado'); si no, borrado físico.

    Efectos: flash + redirect a /productos.
    """
    try:
        call_proc("sp_eliminar_producto", [id])
        flash("Producto eliminado/descontinuado.", "info")
    except Exception as e:
        flash(f"Error al eliminar: {e}", "danger")
    return redirect(url_for("productos_lista"))


# --- Presentaciones ---

@app.route("/presentaciones/nueva/<int:id_producto>", methods=["GET", "POST"])
@handle_form_errors
def presentacion_nueva(id_producto):
    """Crea una presentación (tamaño + precio) para un producto.

    Args:
        id_producto: producto padre (path int).

    Form (POST):
        tamano: varchar(20), ej. "1", "500", "1.5".
        unidad_medida: ml | L | g | kg | Unidad.
        precio_venta: decimal(>0).
        descripcion: opcional.

    SPs:
        sp_insertar_presentacion (5 IN + 1 OUT id_presentacion).

    Template:
        productos/form_presentacion.html.

    Efectos: redirige al detalle del producto tras éxito.
    """
    if request.method == "POST":
        try:
            call_proc_named(
                "sp_insertar_presentacion",
                [
                    id_producto,
                    request.form["tamano"],
                    request.form["unidad_medida"],
                    form_get("precio_venta", float),
                    request.form.get("descripcion") or None,
                ],
                constants.SP_OUT["sp_insertar_presentacion"],
            )
            flash("Presentación registrada.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        return redirect(url_for("producto_detalle", id=id_producto))
    prod = call_proc("sp_consultar_productos", [id_producto])
    unidades = constants.UNIDADES_MEDIDA
    return render_template("productos/form_presentacion.html",
                           producto=prod[0][0] if prod and prod[0] else None,
                           unidades=unidades)


# --- Lotes ---

@app.route("/lotes/nuevo/<int:id_producto>", methods=["GET", "POST"])
@handle_form_errors
def lote_nuevo(id_producto):
    """Crea un lote con stock inicial para un producto.

    Args:
        id_producto: producto padre (path int).

    Form (POST):
        numero_lote: identificador de lote del fabricante.
        fecha_elaboracion, fecha_vencimiento: ISO date.
        cantidad: unidades producidas (= disponibles al inicio).

    SPs:
        sp_insertar_lote (5 IN + 1 OUT id_lote).

    Template:
        productos/form_lote.html.

    Notes:
        El trigger `trg_detalle_after_insert` descontará stock cuando
        se venda. Este SP solo crea el lote; las ventas se controlan
        desde el módulo de facturación.

    Efectos: redirige al detalle del producto tras éxito.
    """
    if request.method == "POST":
        try:
            call_proc_named(
                "sp_insertar_lote",
                [
                    id_producto,
                    request.form["numero_lote"],
                    request.form["fecha_elaboracion"],
                    request.form["fecha_vencimiento"],
                    form_get("cantidad", int),
                ],
                constants.SP_OUT["sp_insertar_lote"],
            )
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
    """Lista los clientes con búsqueda y paginación.

    Query params:
        q: texto a buscar en razon_social, nombre o ruta_nombre.

    SPs:
        sp_consultar_clientes(NULL)

    Template:
        clientes/index.html
    """
    rows = call_proc("sp_consultar_clientes", [None])
    all_items = rows[0] if rows else []
    q = (request.args.get("q") or "").strip().lower()
    if q:
        all_items = [c for c in all_items
                     if q in (c.get("razon_social") or "").lower()
                     or q in (c.get("nombre") or "").lower()
                     or q in (c.get("ruta_nombre") or "").lower()]
    items, pager = paginate(all_items, per_page=20)
    return render_template("clientes/index.html",
                           clientes=items, pager=pager, q=q)


@app.route("/clientes/nuevo", methods=["GET", "POST"])
def cliente_nuevo():
    """Crea un cliente (persona + cliente + teléfono opcional).

    Form (POST):
        nombre: nombre de la persona de contacto.
        razon_social: nombre comercial / jurídico del cliente.
        direccion: dirección de entrega (direccion_compuesta).
        credito: "1" si tiene crédito autorizado, ausente si no.
        id_ruta: ruta de distribución asignada (opcional).
        telefono: número en formato XXXX-XXXX (opcional).
        tipo_telefono: Móvil | Fijo | WhatsApp (default Móvil).

    SPs:
        sp_insertar_cliente (5 IN + 2 OUT: id_cliente, id_persona).
        sp_insertar_telefono (3 IN) — solo si se proporcionó teléfono.

    Notes:
        El cliente y la persona se crean atómicamente dentro del SP
        (transactional). El teléfono se inserta en una llamada
        separada porque no todas las personas tienen.

    Template:
        clientes/form.html (con rutas en el dropdown).

    Efectos: flash + redirect a /clientes tras éxito.
    """
    if request.method == "POST":
        try:
            _, out = call_proc_named(
                "sp_insertar_cliente",
                [
                    request.form["nombre"],
                    request.form["razon_social"],
                    request.form["direccion"],
                    request.form.get("credito") == "1",
                    request.form.get("id_ruta") or None,
                ],
                constants.SP_OUT["sp_insertar_cliente"],
            )
            tel = request.form.get("telefono", "").strip()
            if tel and out.get("id_persona"):
                call_proc("sp_insertar_telefono", [
                    out["id_persona"],
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
    """Detalle del cliente: teléfonos + facturas emitidas.

    Args:
        id: id_cliente.

    SPs:
        sp_consultar_clientes(id) → incluye id_persona desde fase 3.
        sp_consultar_telefonos(id_persona).
        sp_consultar_facturas(id_cliente, NULL, NULL) — todas las facturas.

    Template:
        clientes/detail.html (cards de info + tabla de facturas).

    Notes:
        Antes este endpoint hacía un SELECT extra sobre `persona` para
        obtener `id_persona`. Ahora el SP lo retorna directamente,
        eliminando un round-trip.
    """
    rows = call_proc_dict("sp_consultar_clientes", [id])
    if not rows:
        flash("Cliente no encontrado.", "warning")
        return redirect(url_for("clientes_lista"))
    cliente = rows[0]
    # id_persona viene ahora en el SP (fase 3); antes hacía un SELECT extra
    telefonos = call_proc("sp_consultar_telefonos", [cliente["id_persona"]])
    facturas  = call_proc("sp_consultar_facturas", [id, None, None])
    return render_template("clientes/detail.html",
                           cliente=cliente,
                           telefonos=telefonos[0] if telefonos else [],
                           facturas=facturas[0] if facturas else [])


@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
def cliente_editar(id):
    """Edita los datos editables de un cliente.

    Form (POST):
        nombre, razon_social, direccion, credio ("1"/ausente),
        id_ruta (opcional), estado.

    SPs:
        sp_modificar_cliente (6 IN).
        sp_consultar_clientes(id), sp_consultar_rutas(NULL) — solo GET.

    Template:
        clientes/form.html.

    Efectos: flash + redirect a /clientes/<id>.
    """
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
    estados = constants.ESTADOS_CLIENTE
    return render_template("clientes/form.html",
                           cliente=rows[0][0] if rows and rows[0] else None,
                           rutas=rutas[0] if rutas else [],
                           estados=estados)


@app.route("/clientes/<int:id>/eliminar", methods=["POST"])
def cliente_eliminar(id):
    """Desactiva un cliente (borrado lógico por defecto).

    SPs:
        sp_eliminar_cliente — si tiene facturas, solo cambia estado a
        'Inactivo' (borrado lógico); si no tiene, borrado físico.

    Efectos: flash + redirect a /clientes.
    """
    try:
        call_proc("sp_eliminar_cliente", [id])
        flash("Cliente eliminado.", "info")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("clientes_lista"))


# ============================================================
# MÓDULO: RUTAS Y REPARTIDORES
# ============================================================

@app.route("/rutas")
def rutas_lista():
    """Lista todas las rutas de distribución.

    SPs:
        sp_consultar_rutas(NULL).

    Template:
        rutas/index.html.
    """
    rutas = call_proc("sp_consultar_rutas", [None])
    return render_template("rutas/index.html", rutas=rutas[0] if rutas else [])


@app.route("/rutas/nueva", methods=["GET", "POST"])
def ruta_nueva():
    """Crea una ruta de distribución.

    Form (POST):
        nombre: nombre de la ruta (validado no vacío en SQL).
        zona_geografica: zona/región cubierta.
        descripcion: opcional.

    SPs:
        sp_insertar_ruta (3 IN + 1 OUT id_ruta).

    Template:
        rutas/form.html.

    Efectos: flash + redirect a /rutas.
    """
    if request.method == "POST":
        try:
            call_proc_named(
                "sp_insertar_ruta",
                [
                    request.form["nombre"],
                    request.form["zona_geografica"],
                    request.form.get("descripcion") or None,
                ],
                constants.SP_OUT["sp_insertar_ruta"],
            )
            flash("Ruta registrada.", "success")
            return redirect(url_for("rutas_lista"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("rutas/form.html", ruta=None)


@app.route("/rutas/<int:id>")
def ruta_detalle(id):
    """Detalle de ruta con asignaciones y recorridos históricos.

    Args:
        id: id_ruta.

    SPs:
        sp_consultar_rutas(id).
        sp_consultar_asignaciones(id_ruta, NULL).
        sp_consultar_recorridos(id_ruta, NULL).

    Template:
        rutas/detail.html.

    Efectos: si la ruta no existe, flash + redirect a /rutas.
    """
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
    """Edita nombre, zona, descripción y estado de una ruta.

    Form (POST):
        nombre, zona_geografica, descripcion (opcional), estado.

    SPs:
        sp_modificar_ruta (4 IN).
        sp_consultar_rutas(id) — solo GET.

    Template:
        rutas/form.html.

    Efectos: flash + redirect a /rutas/<id>.
    """
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
    estados = constants.ESTADOS_RUTA
    return render_template("rutas/form.html",
                           ruta=rutas[0][0] if rutas and rutas[0] else None,
                           estados=estados)


@app.route("/rutas/<int:id>/eliminar", methods=["POST"])
def ruta_eliminar(id):
    """Desactiva una ruta.

    SPs:
        sp_eliminar_ruta — equivalente a poner estado 'Inactiva' si
        tiene recorridos asociados.

    Efectos: flash + redirect a /rutas.
    """
    try:
        call_proc("sp_eliminar_ruta", [id])
        flash("Ruta eliminada.", "info")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("rutas_lista"))


# --- Recorridos ---

@app.route("/recorridos/nuevo", methods=["GET", "POST"])
@handle_form_errors
def recorrido_nuevo():
    """Crea un recorrido (turno de entrega en una fecha).

    Form (POST):
        id_ruta, id_repartidor (int), fecha (opcional, default hoy),
        turno: Mañana | Tarde | Noche.

    SPs:
        sp_trx_crear_recorrido (4 IN + 2 OUT: id_recorrido, mensaje).
        sp_consultar_rutas(NULL), sp_consultar_repartidores(NULL) — solo GET.

    Notes:
        El SP valida que repartidor y ruta estén activos. Si no hay
        asignación activa para esa combinación, la crea automáticamente.

    Template:
        rutas/form_recorrido.html.

    Efectos: usa `flash_out` para interpretar el prefijo "OK:" del OUT
    `mensaje` como éxito; redirige a /rutas/<id> tras crear.
    """
    if request.method == "POST":
        try:
            id_ruta = form_get("id_ruta", int)
            _, out = call_proc_named(
                "sp_trx_crear_recorrido",
                [
                    id_ruta,
                    form_get("id_repartidor", int),
                    request.form["fecha"] or None,
                    request.form["turno"],
                ],
                constants.SP_OUT["sp_trx_crear_recorrido"],
            )
            flash_out(out, fallback_danger="Error al crear recorrido.")
            if out.get("id_recorrido"):
                return redirect(url_for("ruta_detalle", id=id_ruta))
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
    """Lista todos los repartidores.

    SPs:
        sp_consultar_repartidores(NULL).

    Template:
        repartidores/index.html.
    """
    rows = call_proc("sp_consultar_repartidores", [None])
    return render_template("repartidores/index.html", repartidores=rows[0] if rows else [])


@app.route("/repartidores/nuevo", methods=["GET", "POST"])
def repartidor_nuevo():
    """Crea un repartidor (persona + licencia).

    Form (POST):
        nombre, licencia (no vacía, validada en SQL).

    SPs:
        sp_insertar_repartidor (2 IN + 1 OUT id_repartidor).

    Template:
        repartidores/form.html.

    Efectos: flash + redirect a /repartidores.
    """
    if request.method == "POST":
        try:
            call_proc_named(
                "sp_insertar_repartidor",
                [request.form["nombre"], request.form["licencia"]],
                constants.SP_OUT["sp_insertar_repartidor"],
            )
            flash("Repartidor registrado.", "success")
            return redirect(url_for("repartidores_lista"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("repartidores/form.html", repartidor=None)


@app.route("/repartidores/<int:id>/editar", methods=["GET", "POST"])
def repartidor_editar(id):
    """Edita nombre, licencia y estado de un repartidor.

    Form (POST):
        nombre, licencia, estado (Activo | Inactivo | Suspendido).

    SPs:
        sp_modificar_repartidor (3 IN).
        sp_consultar_repartidores(id) — solo GET.

    Template:
        repartidores/form.html.

    Efectos: flash + redirect a /repartidores.
    """
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
    estados = constants.ESTADOS_REPARTIDOR
    return render_template("repartidores/form.html",
                           repartidor=rows[0][0] if rows and rows[0] else None,
                           estados=estados)


@app.route("/repartidores/<int:id>/eliminar", methods=["POST"])
def repartidor_eliminar(id):
    """Desactiva un repartidor.

    SPs:
        sp_eliminar_repartidor — equivalente a 'Inactivo'.

    Efectos: flash + redirect a /repartidores.
    """
    try:
        call_proc("sp_eliminar_repartidor", [id])
        flash("Repartidor eliminado.", "info")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for("repartidores_lista"))


# ============================================================
# MÓDULO: FACTURACIÓN
# ============================================================

@app.route("/facturacion")
def facturacion_lista():
    """Lista facturas con filtros por cliente y rango de fechas.

    Query params:
        desde, hasta: fechas ISO (YYYY-MM-DD), opcionales.
        cliente: id_cliente, opcional.
        page: paginación (default 1).

    SPs:
        sp_consultar_facturas(id_cliente, desde, hasta).

    Template:
        facturacion/index.html (con dropdown de clientes para filtro).

    Notes:
        La paginación se hace en memoria sobre el resultado del SP;
        si el volumen crece conviene mover LIMIT/OFFSET al SP.
    """
    fecha_desde = request.args.get("desde") or None
    fecha_hasta = request.args.get("hasta") or None
    id_cliente  = request.args.get("cliente") or None
    page        = request.args.get("page", 1)
    rows = call_proc("sp_consultar_facturas", [id_cliente, fecha_desde, fecha_hasta])
    all_items = rows[0] if rows else []
    items, pager = paginate(all_items, per_page=25)
    clientes = call_proc("sp_consultar_clientes", [None])
    return render_template("facturacion/index.html",
                           facturas=items, pager=pager,
                           clientes=clientes[0] if clientes else [],
                           filtros={"desde": fecha_desde, "hasta": fecha_hasta, "cliente": id_cliente})


@app.route("/facturacion/nueva", methods=["GET", "POST"])
@handle_form_errors
def factura_nueva():
    """Crea una factura (Contado o Crédito).

    Form (POST):
        id_cliente, id_repartidor, id_recorrido (ints).
        condicion_pago: Contado | Crédito.
        id_presentacion, id_lote (ints).
        cantidad (int > 0).
        monto_recibido (float): solo Contado.
        fecha_vencimiento_credito, limite_credito: solo Crédito.

    SPs:
        sp_trx_crear_factura_completa (10 IN + 3 OUT: id_factura,
        numero_factura, mensaje).
        sp_consultar_clientes/repartidores/recorridos + vista_catalogo
        solo para popular el form (GET).

    Notes:
        Los campos específicos de Contado/Crédito se pasan como None
        cuando no aplican (el SP los ignora según `p_condicion_pago`).
        Validaciones críticas (stock, crédito autorizado, fechas) se
        hacen en el SP, no en el endpoint.

    Template:
        facturacion/nueva.html (con JS que muestra/oculta campos según
        condición de pago y autocompleta lote desde la presentación).

    Efectos: redirige a /facturacion/<id> tras éxito.
    """
    if request.method == "POST":
        try:
            id_cliente      = form_get("id_cliente", int)
            id_repartidor   = form_get("id_repartidor", int)
            id_recorrido    = form_get("id_recorrido", int)
            condicion       = request.form["condicion_pago"]
            id_presentacion = form_get("id_presentacion", int)
            id_lote         = form_get("id_lote", int)
            cantidad        = form_get("cantidad", int)
            monto_rec       = form_get("monto_recibido", float, default=0)
            fecha_venc      = request.form.get("fecha_vencimiento_credito") or None
            limite_cred     = form_get("limite_credito", float, default=0)

            _, out = call_proc_named(
                "sp_trx_crear_factura_completa",
                [
                    id_cliente, id_repartidor, id_recorrido, condicion,
                    id_presentacion, id_lote, cantidad,
                    monto_rec if condicion == "Contado" else None,
                    fecha_venc if condicion == "Crédito" else None,
                    limite_cred if condicion == "Crédito" else None,
                ],
                constants.SP_OUT["sp_trx_crear_factura_completa"],
            )
            flash_out(out, fallback_danger="Error desconocido al crear factura.")
            if out.get("id_factura"):
                return redirect(url_for("factura_detalle", id=out["id_factura"]))
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
    """Detalle completo de una factura: encabezado, ítems, pagos, crédito.

    Args:
        id: id_factura.

    SPs:
        sp_consultar_factura(id) → encabezado.
        sp_consultar_detalles(id) → líneas de producto.
        sp_consultar_pagos(id) → pagos parciales (si es crédito).
        sp_consultar_factura_credito(id) → saldo + vencimiento.

    Template:
        facturacion/detalle.html (cuatro cards: info, crédito, pagos,
        detalle de productos + acciones condicionales según estado).

    Efectos: si la factura no existe, flash + redirect.
    """
    rows     = call_proc("sp_consultar_factura", [id])
    factura  = rows[0][0] if rows and rows[0] else None
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
@handle_form_errors
def factura_pagar(id):
    """Registra un pago parcial o total de una factura a crédito.

    Form (POST):
        monto (float > 0, <= saldo).
        metodo_pago: Efectivo | Transferencia | SINPE | Cheque.
        comprobante: número/texto opcional.

    SPs:
        sp_trx_registrar_pago (4 IN + 3 OUT: id_pago, saldo_restante,
        mensaje).
        sp_consultar_factura_credito(id) — solo GET, para mostrar el
        saldo pendiente en el form.

    Notes:
        El trigger `trg_pago_after_insert` actualiza automáticamente
        el saldo y, si llega a 0, marca la factura como 'Pagada'. El
        SP solo lee el saldo resultante para devolverlo al cliente.

    Template:
        facturacion/pago.html.

    Efectos: flash + redirect a /facturacion/<id>.
    """
    if request.method == "POST":
        try:
            _, out = call_proc_named(
                "sp_trx_registrar_pago",
                [
                    id,
                    form_get("monto", float),
                    request.form["metodo_pago"],
                    request.form.get("comprobante") or None,
                ],
                constants.SP_OUT["sp_trx_registrar_pago"],
            )
            flash_out(out, fallback_danger="Pago no registrado.")
        except Exception as e:
            flash(f"Error al registrar pago: {e}", "danger")
        return redirect(url_for("factura_detalle", id=id))
    credito = call_proc("sp_consultar_factura_credito", [id])
    return render_template("facturacion/pago.html",
                           id_factura=id,
                           credito=credito[0][0] if credito and credito[0] else None)


@app.route("/facturacion/<int:id>/anular", methods=["POST"])
def factura_anular(id):
    """Anula una factura (restaura stock vía cursor; solo si es válida).

    Args:
        id: id_factura.

    SPs:
        sp_trx_anular_factura (1 IN + 1 OUT mensaje).

    Notas de negocio:
        - Solo se permite si estado IN ('Emitida', 'Pendiente').
        - Si es Crédito con pagos, se rechaza (hay que reversar pagos
          primero; ver README "Troubleshooting").

    Efectos: flash + redirect a /facturacion/<id>.
    """
    try:
        _, out = call_proc_named(
            "sp_trx_anular_factura",
            [id],
            constants.SP_OUT["sp_trx_anular_factura"],
        )
        flash_out(out, fallback_danger="No se pudo anular la factura.")
    except Exception as e:
        flash(f"Error al anular: {e}", "danger")
    return redirect(url_for("factura_detalle", id=id))


@app.route("/facturacion/<int:id>/eliminar", methods=["POST"])
def factura_eliminar(id):
    """Alias histórico de `factura_anular` (mismo SP, distinto template).

    Conservado por compatibilidad con templates antiguos que usan
    `/eliminar` en lugar de `/anular`. La semántica es idéntica:
    marca la factura como 'Anulada' y restaura stock. No es borrado
    físico.
    """
    try:
        _, out = call_proc_named(
            "sp_trx_anular_factura",
            [id],
            constants.SP_OUT["sp_trx_anular_factura"],
        )
        flash_out(out, fallback_danger="Factura no anulada.")
    except Exception as e:
        flash(f"Error al eliminar: {e}", "danger")
    return redirect(url_for("factura_detalle", id=id))


# ============================================================
# MÓDULO: REPORTES
# ============================================================

@app.route("/reportes/ventas-por-ruta")
def rpt_ventas_ruta():
    """Reporte de ventas agrupadas por ruta y fecha.

    Query params:
        desde, hasta: fechas ISO, opcionales (sin filtro = todas las
                      ventas).

    SPs:
        sp_rpt_ventas_por_ruta(desde, hasta).

    Template:
        reportes/ventas_ruta.html.
    """
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    rows  = call_proc("sp_rpt_ventas_por_ruta", [desde, hasta])
    return render_template("reportes/ventas_ruta.html",
                           datos=rows[0] if rows else [],
                           filtros={"desde": desde, "hasta": hasta})


@app.route("/reportes/creditos")
def rpt_creditos():
    """Resumen de clientes con créditos pendientes (cálculo con cursor).

    SPs:
        sp_cur_resumen_creditos — recorre clientes con deudas, calcula
        total adeudado y factura más antigua, vuelca a tabla temporal.

    Template:
        reportes/creditos.html.
    """
    rows = call_proc("sp_cur_resumen_creditos")
    return render_template("reportes/creditos.html",
                           datos=rows[0] if rows else [])


@app.route("/reportes/productos-por-vencer")
def rpt_productos_vencer():
    """Lotes cuya fecha de vencimiento está dentro de N días.

    Query params:
        dias: ventana en días (default 30).

    SPs:
        sp_rpt_productos_proximos_vencer(dias).

    Template:
        reportes/productos_vencer.html.
    """
    dias = int(request.args.get("dias", 30))
    rows = call_proc("sp_rpt_productos_proximos_vencer", [dias])
    return render_template("reportes/productos_vencer.html",
                           datos=rows[0] if rows else [], dias=dias)


@app.route("/reportes/top-productos")
def rpt_top_productos():
    """Productos más vendidos por cantidad en un rango de fechas.

    Query params:
        desde, hasta: fechas ISO, opcionales.

    SPs:
        sp_rpt_top_productos_vendidos(desde, hasta, NULL). El último
        NULL es el id_cliente (para top por cliente específico).

    Template:
        reportes/top_productos.html.
    """
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None
    rows  = call_proc("sp_rpt_top_productos_vendidos", [desde, hasta, None])
    return render_template("reportes/top_productos.html",
                           datos=rows[0] if rows else [],
                           filtros={"desde": desde, "hasta": hasta})


if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
