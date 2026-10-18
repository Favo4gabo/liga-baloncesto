"""Consultas financieras y descargas de reportes, sin permitir marcar pagos."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..authz import roles_required, usuario_actual
from ..database import db
from ..models import AsignacionPartido, GastoReal, Partido, TasaCambioBCV
from ..services.bcv import consultar_tasa_bcv, tasa_para_fecha
from ..services.auditoria import registrar_cambio

bp = Blueprint("finanzas", __name__)
CATEGORIAS = (
    ("transporte_externo", "Transporte externo", "costo_traslado_externo"),
    ("transporte_interno", "Transporte interno", "costo_traslado_interno"),
    ("hospedaje", "Hospedaje", "costo_estadia"),
    ("viaticos", "Viáticos", "costo_viaticos"),
    ("gastos_extra", "Gastos extra aprobados", None),
)
CATEGORIAS_GASTO_REAL = {"transporte_externo", "transporte_interno", "hospedaje", "viaticos"}
GRUPOS = {"arbitro", "partido", "ciudad", "temporada"}
ROLES_DESCARGA = ("super_admin", "admin", "accountant")


def _mes(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m").date().replace(day=1)
    except ValueError as error:
        raise ValueError("mes debe tener formato YYYY-MM.") from error


def _fecha(valor, campo):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as error:
        raise ValueError(f"{campo} debe tener formato YYYY-MM-DD.") from error


def _tasa_cache(fecha, cache):
    clave = fecha.isoformat()
    if clave not in cache:
        registro = tasa_para_fecha(fecha, auto_consultar_hoy=False)
        cache[clave] = registro
    return cache[clave]


def _movimientos(args):
    mes = _mes(args.get("mes"))
    desde = _fecha(args.get("desde"), "desde")
    hasta = _fecha(args.get("hasta"), "hasta")
    temporada = args.get("temporada")
    if temporada:
        try:
            anio = int(temporada)
            if anio < 2000 or anio > 2200:
                raise ValueError
        except ValueError as error:
            raise ValueError("temporada debe ser un año válido.") from error
        desde, hasta, mes = date(anio, 1, 1), date(anio, 12, 31), None
    if mes:
        desde = mes
        hasta = (mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    query = Partido.query.order_by(Partido.fecha_hora.asc())
    if desde:
        query = query.filter(Partido.fecha_hora >= datetime.combine(desde, time.min))
    if hasta:
        query = query.filter(Partido.fecha_hora < datetime.combine(hasta + timedelta(days=1), time.min))
    def optional_int(field):
        raw = args.get(field)
        if raw in (None, ""):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{field} debe ser un entero.") from error
        if str(value) != str(raw).strip():
            raise ValueError(f"{field} debe ser un entero.")
        return value

    ciudad_id = optional_int("ciudad_id")
    if ciudad_id:
        query = query.filter(Partido.ciudad_juego_id == ciudad_id)

    arbitro_id = optional_int("arbitro_id")
    tasas_cache = {}
    movimientos = []
    for partido in query.all():
        for asignacion in partido.asignaciones:
            if arbitro_id and asignacion.arbitro_id != arbitro_id:
                continue
            # El presupuesto se convierte con la tasa vigente el día del partido;
            # el gasto real usa su propia fecha de factura/gasto más abajo.
            fecha_conversion = min(partido.fecha_hora.date(), date.today())
            tasa = _tasa_cache(fecha_conversion, tasas_cache)
            rate = Decimal(str(tasa.ves_por_usd)) if tasa else None
            costos_usd = {key: Decimal(str(getattr(asignacion, column) or 0)) if column else Decimal("0") for key, _, column in CATEGORIAS}
            total_usd = sum((costos_usd[key] for key, _, column in CATEGORIAS if column), Decimal("0"))
            costos_ves = {key: amount * rate for key, amount in costos_usd.items()} if rate else None
            total_ves = total_usd * rate if rate else None
            gastos_reales = [gasto for gasto in asignacion.gastos_reales if not gasto.anulado]
            real_usd = {key: Decimal("0") for key, _, _ in CATEGORIAS}
            real_ves = {key: Decimal("0") for key, _, _ in CATEGORIAS}
            gastos_reales_data = []
            real_sin_tasa = 0
            for gasto in gastos_reales:
                amount_usd = Decimal(str(gasto.monto_usd))
                if gasto.moneda == "VES":
                    amount_ves = Decimal(str(gasto.monto_original))
                    actual_rate = Decimal(str(gasto.tasa_bcv)) if gasto.tasa_bcv else None
                    tasa_actual = None
                else:
                    tasa_actual = _tasa_cache(gasto.fecha_gasto, tasas_cache)
                    actual_rate = Decimal(str(tasa_actual.ves_por_usd)) if tasa_actual else None
                    amount_ves = amount_usd * actual_rate if actual_rate else None
                real_usd[gasto.categoria] += amount_usd
                if amount_ves is not None:
                    real_ves[gasto.categoria] += amount_ves
                else:
                    real_sin_tasa += 1
                gastos_reales_data.append({
                    **gasto.to_dict(),
                    "tipo": "gasto_real",
                    "tasa_fecha": tasa_actual.fecha.isoformat() if tasa_actual else (gasto.fecha_gasto.isoformat() if gasto.moneda == "VES" and gasto.tasa_bcv else None),
                    "monto_ves": float(amount_ves.quantize(Decimal("0.01"))) if amount_ves is not None else None,
                })
            gastos_extra_aprobados = [extra for extra in asignacion.gastos_extra if extra.estado == "Aprobado"]
            gastos_extra_pendientes = [extra.to_dict() for extra in asignacion.gastos_extra if extra.estado == "Pendiente"]
            for extra in gastos_extra_aprobados:
                if extra.moneda == "VES":
                    tasa_extra = _tasa_cache(extra.reportado_en.date(), tasas_cache)
                    extra_rate = Decimal(str(tasa_extra.ves_por_usd)) if tasa_extra else None
                    extra_usd = Decimal(str(extra.monto)) / extra_rate if extra_rate else Decimal("0")
                    extra_ves = Decimal(str(extra.monto)) if extra_rate else None
                else:
                    tasa_extra = _tasa_cache(extra.reportado_en.date(), tasas_cache)
                    extra_rate = Decimal(str(tasa_extra.ves_por_usd)) if tasa_extra else None
                    extra_usd = Decimal(str(extra.monto))
                    extra_ves = extra_usd * extra_rate if extra_rate else None
                real_usd["gastos_extra"] += extra_usd
                if extra_ves is None:
                    real_sin_tasa += 1
                else:
                    real_ves["gastos_extra"] += extra_ves
                gastos_reales_data.append({
                    "id": extra.id,
                    "tipo": "gasto_extra",
                    "asignacion_id": asignacion.id,
                    "categoria": "gastos_extra",
                    "fecha_gasto": extra.reportado_en.date().isoformat(),
                    "monto_original": float(Decimal(str(extra.monto))),
                    "moneda": extra.moneda,
                    "monto_usd": float(extra_usd.quantize(Decimal("0.01"))),
                    "monto_ves": float(extra_ves.quantize(Decimal("0.01"))) if extra_ves is not None else None,
                    "tasa_bcv": float(extra_rate) if extra_rate else None,
                    "tasa_fecha": tasa_extra.fecha.isoformat() if tasa_extra else None,
                    "descripcion": f"{extra.concepto}: {extra.descripcion or ''}".strip(),
                    "referencia_documento": None,
                    "anulado": False,
                })
            real_total_usd = sum(real_usd.values(), Decimal("0"))
            real_total_ves = sum(real_ves.values(), Decimal("0")) if real_sin_tasa == 0 else None
            movimientos.append({
                "asignacion_id": asignacion.id,
                "partido_id": partido.id,
                "fecha_partido": partido.fecha_hora.isoformat(),
                "mes_partido": partido.fecha_hora.strftime("%Y-%m"),
                "temporada": partido.fecha_hora.year,
                "estadio": partido.estadio_cancha,
                "ciudad_id": partido.ciudad_juego_id,
                "ciudad": partido.ciudad_juego.nombre if partido.ciudad_juego else "",
                "estado": partido.ciudad_juego.estado.nombre if partido.ciudad_juego and partido.ciudad_juego.estado else "",
                "arbitro_id": asignacion.arbitro_id,
                "arbitro": f"{asignacion.arbitro.nombre} {asignacion.arbitro.apellido}" if asignacion.arbitro else "",
                "fecha_tasa": tasa.fecha.isoformat() if tasa else None,
                "fuente_tasa": tasa.fuente if tasa else None,
                "ves_por_usd": float(rate) if rate else None,
                "costos_usd": {key: float(value) for key, value in costos_usd.items()},
                "total_usd": float(total_usd),
                "costos_ves": {key: float(value.quantize(Decimal("0.01"))) for key, value in costos_ves.items()} if costos_ves else None,
                "total_ves": float(total_ves.quantize(Decimal("0.01"))) if total_ves is not None else None,
                "conversion_estimada": partido.fecha_hora.date() > date.today() or tasa is None,
                "real_usd": {key: float(value) for key, value in real_usd.items()},
                "real_ves": {key: float(value.quantize(Decimal("0.01"))) for key, value in real_ves.items()},
                "total_real_usd": float(real_total_usd),
                "total_real_ves": float(real_total_ves.quantize(Decimal("0.01"))) if real_total_ves is not None else None,
                "variacion_usd": float(real_total_usd - total_usd) if gastos_reales_data else None,
                "gastos_reales": gastos_reales_data,
                "gastos_extra_pendientes": gastos_extra_pendientes,
                "cantidad_gastos_reales": len(gastos_reales_data),
                "gastos_reales_sin_tasa": real_sin_tasa,
            })
    return movimientos


def _totales(movimientos):
    total_usd = sum((Decimal(str(item["total_usd"])) for item in movimientos), Decimal("0"))
    converted = [item for item in movimientos if item["total_ves"] is not None]
    total_ves = sum((Decimal(str(item["total_ves"])) for item in converted), Decimal("0"))
    categorias = {}
    for key, label, _ in CATEGORIAS:
        usd = sum((Decimal(str(item["costos_usd"][key])) for item in movimientos), Decimal("0"))
        ves = sum((Decimal(str(item["costos_ves"][key])) for item in converted), Decimal("0"))
        real_usd = sum((Decimal(str(item["real_usd"][key])) for item in movimientos), Decimal("0"))
        real_ves = sum((Decimal(str(item["real_ves"][key])) for item in movimientos), Decimal("0"))
        missing_real_rate = any(
            expense["categoria"] == key and expense["monto_ves"] is None
            for item in movimientos for expense in item["gastos_reales"]
        )
        categorias[key] = {
            "nombre": label,
            "usd": float(usd),
            "ves": float(ves.quantize(Decimal("0.01"))),
            "real_usd": float(real_usd),
            "real_ves": float(real_ves.quantize(Decimal("0.01"))) if not missing_real_rate else None,
            "variacion_usd": float(real_usd - usd) if any(item["real_usd"][key] for item in movimientos) else None,
        }
    total_real_usd = sum((Decimal(str(item["total_real_usd"])) for item in movimientos), Decimal("0"))
    actual_conversiones_completas = all(
        expense["monto_ves"] is not None
        for item in movimientos for expense in item["gastos_reales"]
    )
    total_real_ves = sum((Decimal(str(item["total_real_ves"])) for item in movimientos if item["total_real_ves"] is not None), Decimal("0"))
    tiene_gastos_reales = sum(item["cantidad_gastos_reales"] for item in movimientos) > 0
    return {
        "usd": float(total_usd),
        "ves": float(total_ves.quantize(Decimal("0.01"))),
        "real_usd": float(total_real_usd),
        "real_ves": float(total_real_ves.quantize(Decimal("0.01"))) if actual_conversiones_completas and tiene_gastos_reales else None,
        "variacion_usd": float(total_real_usd - total_usd) if tiene_gastos_reales else None,
        "asignaciones": len(movimientos),
        "asignaciones_con_gasto_real": sum(1 for item in movimientos if item["cantidad_gastos_reales"]),
        "registros_gasto_real": sum(item["cantidad_gastos_reales"] for item in movimientos),
        "sin_tasa": len(movimientos) - len(converted),
        "categorias": categorias,
    }


def _agrupar(movimientos, grupo):
    getters = {
        "arbitro": lambda item: (item["arbitro_id"], item["arbitro"]),
        "partido": lambda item: (item["partido_id"], f"{item['estadio']} · {item['fecha_partido'][:10]}"),
        "ciudad": lambda item: (item["ciudad_id"], f"{item['ciudad']}, {item['estado']}"),
        "temporada": lambda item: (item["temporada"], str(item["temporada"])),
    }
    grouped = {}
    for item in movimientos:
        key, label = getters[grupo](item)
        row = grouped.setdefault(key, {"id": key, "nombre": label, "asignaciones": 0, "usd": 0.0, "ves": 0.0, "real_usd": 0.0, "real_ves": 0.0, "variacion_usd": 0.0, "gastos_reales": 0, "sin_tasa_real": 0, "sin_registro_real": True, **{k: 0.0 for k, _, _ in CATEGORIAS}, **{f"real_{k}": 0.0 for k, _, _ in CATEGORIAS}})
        row["asignaciones"] += 1
        row["usd"] += item["total_usd"]
        row["real_usd"] += item["total_real_usd"]
        if item["cantidad_gastos_reales"]:
            row["sin_registro_real"] = False
            row["gastos_reales"] += item["cantidad_gastos_reales"]
            row["sin_tasa_real"] += item["gastos_reales_sin_tasa"]
        if item["total_ves"] is not None:
            row["ves"] += item["total_ves"]
        if item["total_real_ves"] is not None:
            row["real_ves"] += item["total_real_ves"]
        for category, _, _ in CATEGORIAS:
            row[category] += item["costos_usd"][category]
            row[f"real_{category}"] += item["real_usd"][category]
    for row in grouped.values():
        row["variacion_usd"] = row["real_usd"] - row["usd"] if not row["sin_registro_real"] else None
        if row["sin_tasa_real"]:
            row["real_ves"] = None
    return sorted(grouped.values(), key=lambda row: row["nombre"])


@bp.get("/resumen")
def resumen_financiero():
    periodo = request.args.get("mes") or date.today().strftime("%Y-%m")
    try:
        _mes(periodo)
        movimientos = _movimientos({"mes": periodo})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    tasa_hoy = _tasa_cache(date.today(), {})
    return jsonify({
        "mes": periodo,
        "moneda_base": "USD",
        "resumen": _totales(movimientos),
        "items": movimientos,
        "tasa_hoy": tasa_hoy.to_dict() if tasa_hoy else None,
        "advertencia_tasas": "Algunos presupuestos o gastos reales no tienen una tasa registrada para la fecha correspondiente; su conversión VES aparece vacía." if any(item["total_ves"] is None or item["gastos_reales_sin_tasa"] for item in movimientos) else None,
    }), 200


@bp.get("/movimientos")
def listar_movimientos_financieros():
    try:
        movimientos = _movimientos(request.args)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"items": movimientos, "totales": _totales(movimientos)}), 200


@bp.post("/gastos-reales")
@roles_required("super_admin", "admin", "accountant")
def registrar_gasto_real():
    datos = request.get_json(silent=True) or {}
    try:
        asignacion_id = int(datos.get("asignacion_id"))
        categoria = str(datos.get("categoria", ""))
        fecha_gasto = date.fromisoformat(str(datos.get("fecha_gasto", "")))
        monto = Decimal(str(datos.get("monto", "")))
        moneda = str(datos.get("moneda", "USD")).upper()
        if categoria not in CATEGORIAS_GASTO_REAL:
            raise ValueError("Selecciona una categoría logística válida.")
        if not monto.is_finite() or monto <= 0:
            raise ValueError("El gasto real debe ser mayor que cero.")
        if moneda not in {"USD", "VES"}:
            raise ValueError("La moneda del gasto debe ser USD o VES.")
        if fecha_gasto > date.today():
            raise ValueError("La fecha del gasto no puede estar en el futuro.")
    except (TypeError, ValueError, InvalidOperation) as error:
        return jsonify({"error": str(error) or "Revisa los datos del gasto."}), 400

    asignacion = db.session.get(AsignacionPartido, asignacion_id)
    if asignacion is None:
        return jsonify({"error": "No existe la asignación indicada."}), 404
    tasa = tasa_para_fecha(fecha_gasto, auto_consultar_hoy=False) if moneda == "VES" else None
    if moneda == "VES" and tasa is None:
        return jsonify({"error": "No hay tasa BCV registrada para esa fecha. Sincroniza o registra la tasa verificada primero."}), 409
    tasa_valor = Decimal(str(tasa.ves_por_usd)) if tasa else None
    monto_usd = monto.quantize(Decimal("0.01")) if moneda == "USD" else (monto / tasa_valor).quantize(Decimal("0.01"))
    gasto = GastoReal(
        asignacion_id=asignacion_id,
        categoria=categoria,
        fecha_gasto=fecha_gasto,
        monto_original=monto.quantize(Decimal("0.01")),
        moneda=moneda,
        monto_usd=monto_usd,
        tasa_bcv=tasa_valor,
        descripcion=str(datos.get("descripcion") or "").strip()[:300] or None,
        referencia_documento=str(datos.get("referencia_documento") or "").strip()[:120] or None,
        creado_por_id=usuario_actual().id,
    )
    db.session.add(gasto)
    db.session.flush()
    registrar_cambio("gasto_real", gasto.id, "CREAR", despues={
        "asignacion_id": asignacion_id,
        "categoria": categoria,
        "fecha_gasto": fecha_gasto.isoformat(),
        "monto_original": str(gasto.monto_original),
        "moneda": moneda,
        "monto_usd": str(gasto.monto_usd),
        "tasa_bcv": str(tasa_valor) if tasa_valor else None,
    })
    return jsonify(gasto.to_dict()), 201


@bp.post("/gastos-reales/<int:gasto_id>/anular")
@roles_required("super_admin", "admin", "accountant")
def anular_gasto_real(gasto_id):
    datos = request.get_json(silent=True) or {}
    motivo = str(datos.get("motivo", "")).strip()
    if len(motivo) < 5:
        return jsonify({"error": "Indica un motivo de al menos 5 caracteres para anular el registro."}), 400
    gasto = db.session.get(GastoReal, gasto_id)
    if gasto is None:
        return jsonify({"error": "Gasto real no encontrado."}), 404
    if gasto.anulado:
        return jsonify({"error": "El gasto ya está anulado."}), 409
    antes = {"anulado": gasto.anulado, "monto_usd": str(gasto.monto_usd)}
    gasto.anulado = True
    gasto.motivo_anulacion = motivo[:300]
    gasto.anulado_por_id = usuario_actual().id
    gasto.anulado_en = datetime.utcnow()
    registrar_cambio("gasto_real", gasto.id, "ANULAR", antes, {
        "anulado": True, "motivo": motivo[:300], "anulado_por_id": usuario_actual().id,
    })
    return jsonify(gasto.to_dict()), 200


@bp.get("/tasas")
def listar_tasas():
    tasas = TasaCambioBCV.query.order_by(TasaCambioBCV.fecha.desc()).limit(400).all()
    return jsonify([tasa.to_dict() for tasa in tasas]), 200


@bp.post("/tasas-bcv/sincronizar")
@roles_required("super_admin", "admin")
def sincronizar_tasa_bcv():
    try:
        tasa = consultar_tasa_bcv(date.today(), usuario_actual().id)
        return jsonify(tasa.to_dict()), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 502


@bp.post("/tasas")
@roles_required("super_admin", "admin")
def registrar_tasa_historica():
    datos = request.get_json(silent=True) or {}
    try:
        efectiva = date.fromisoformat(datos.get("fecha", ""))
        valor = Decimal(str(datos.get("ves_por_usd", "")))
        if not valor.is_finite() or valor <= 0 or efectiva > date.today():
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        return jsonify({"error": "Indica una fecha pasada/hoy y una tasa BCV positiva en bolívares por USD."}), 400
    registro = db.session.get(TasaCambioBCV, efectiva) or TasaCambioBCV(fecha=efectiva)
    registro.ves_por_usd = valor
    registro.fuente = "BCV (registrada por administrador)"
    registro.url_fuente = datos.get("url_fuente") or "https://www.bcv.org.ve/"
    registro.registrada_por_id = usuario_actual().id
    db.session.add(registro)
    db.session.commit()
    return jsonify(registro.to_dict()), 201


def _datos_reporte():
    try:
        movimientos = _movimientos(request.args)
    except ValueError as error:
        return None, None, (jsonify({"error": str(error)}), 400)
    grupo = request.args.get("agrupar", "arbitro")
    if grupo not in GRUPOS:
        return None, None, (jsonify({"error": "agrupar debe ser arbitro, partido, ciudad o temporada."}), 400)
    return movimientos, _agrupar(movimientos, grupo), None


@bp.get("/exportar.xlsx")
@roles_required(*ROLES_DESCARGA)
def exportar_excel():
    movimientos, agrupados, error = _datos_reporte()
    if error:
        return error
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Resumen de gastos"
    hoja.append(["ArbiLiga · Informe financiero", "Moneda base USD; VES usa la tasa BCV efectiva en fecha de pago"])
    hoja.append(["Agrupación", request.args.get("agrupar", "arbitro"), "Filtro mes", request.args.get("mes", "Todos")])
    hoja.append([])
    encabezados = ["Referencia", "Asignaciones", "Presupuesto externo USD", "Presupuesto interno USD", "Presupuesto hospedaje USD", "Presupuesto viáticos USD", "Presupuesto total USD", "Real externo USD", "Real interno USD", "Real hospedaje USD", "Real viáticos USD", "Extras aprobados USD", "Gasto real total USD", "Variación USD", "Gasto real VES", "Registros sin tasa"]
    hoja.append(encabezados)
    for celda in hoja[4]:
        celda.font = Font(color="FFFFFF", bold=True)
        celda.fill = PatternFill("solid", fgColor="17365D")
    for row in agrupados:
        hoja.append([row["nombre"], row["asignaciones"], row["transporte_externo"], row["transporte_interno"], row["hospedaje"], row["viaticos"], row["usd"], row["real_transporte_externo"], row["real_transporte_interno"], row["real_hospedaje"], row["real_viaticos"], row["real_gastos_extra"], row["real_usd"], row["variacion_usd"], row["real_ves"], row["sin_tasa_real"]])
    hoja.freeze_panes = "A5"
    hoja.auto_filter.ref = f"A4:P{max(4, hoja.max_row)}"
    for columna, ancho in {"A": 38, "B": 15, "C": 22, "D": 22, "E": 22, "F": 20, "G": 20, "H": 18, "I": 18, "J": 18, "K": 18, "L": 18, "M": 19, "N": 17, "O": 18, "P": 18}.items():
        hoja.column_dimensions[columna].width = ancho
    stream = BytesIO()
    libro.save(stream)
    stream.seek(0)
    return send_file(stream, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="informe_financiero_arbiliga.xlsx")


@bp.get("/exportar.pdf")
@roles_required(*ROLES_DESCARGA)
def exportar_pdf():
    movimientos, agrupados, error = _datos_reporte()
    if error:
        return error
    grupo = request.args.get("agrupar", "arbitro")
    stream = BytesIO()
    pdf = SimpleDocTemplate(stream, pagesize=landscape(letter), title="Informe financiero ArbiLiga")
    styles = getSampleStyleSheet()
    contenido = [Paragraph("Informe financiero · ArbiLiga", styles["Title"]), Spacer(1, 8)]
    contenido.append(Paragraph(f"Agrupado por {grupo} · Filtro: {request.args.get('mes') or request.args.get('temporada') or 'Todos'} · Presupuesto y gastos reales base en USD; VES requiere tasa registrada para la fecha del gasto.", styles["Normal"]))
    contenido.append(Spacer(1, 14))
    filas = [["Referencia", "Juegos", "Presup. USD", "Real externo", "Real interno", "Real hotel", "Real viáticos", "Extras", "Real total", "Variación", "Real VES"]]
    filas.extend([[str(row["nombre"])[:32], row["asignaciones"], f"{row['usd']:,.2f}", f"{row['real_transporte_externo']:,.2f}", f"{row['real_transporte_interno']:,.2f}", f"{row['real_hospedaje']:,.2f}", f"{row['real_viaticos']:,.2f}", f"{row['real_gastos_extra']:,.2f}", f"{row['real_usd']:,.2f}", f"{row['variacion_usd']:,.2f}" if row["variacion_usd"] is not None else "Sin registro", f"{row['real_ves']:,.2f}" if row["real_ves"] is not None else "Sin tasa"] for row in agrupados])
    tabla = Table(filas, repeatRows=1, hAlign="LEFT")
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    contenido.append(tabla)
    pdf.build(contenido)
    stream.seek(0)
    return send_file(stream, mimetype="application/pdf", as_attachment=True, download_name="informe_financiero_arbiliga.pdf")
