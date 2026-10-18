"""Rutas para partidos y sus asignaciones."""

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..database import db
from ..models import ARBITROS_POR_PARTIDO, Arbitro, AsignacionPartido, Ciudad, ESTADOS_PAGO, ESTADOS_VIAJE, Partido
from ..services.asignaciones import AsignacionError, crear_asignacion
from ..services.calculator import calcular_viaticos_asignacion
from ..services.notifications import registrar_y_enviar_evento

bp = Blueprint("partidos", __name__)


def _fecha_hora(valor):
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError("fecha_hora debe estar en formato ISO 8601.") from error


@bp.get("/partidos")
def listar_partidos():
    partidos = Partido.query.order_by(Partido.fecha_hora).all()
    return jsonify([partido.to_dict() for partido in partidos]), 200


@bp.post("/partidos")
def crear_partido():
    datos = request.get_json(silent=True) or {}
    requeridos = ("fecha_hora", "estadio_cancha", "ciudad_juego_id")
    faltantes = [campo for campo in requeridos if not datos.get(campo)]
    if faltantes:
        return jsonify({"error": "Campos obligatorios: " + ", ".join(faltantes)}), 400
    if db.session.get(Ciudad, datos["ciudad_juego_id"]) is None:
        return jsonify({"error": "La ciudad de juego no existe."}), 400
    try:
        partido = Partido(
            fecha_hora=_fecha_hora(datos["fecha_hora"]),
            estadio_cancha=datos["estadio_cancha"],
            ciudad_juego_id=datos["ciudad_juego_id"],
            estado_partido=datos.get("estado_partido", "Programado"),
        )
        db.session.add(partido)
        db.session.commit()
        return jsonify(partido.to_dict()), 201
    except (ValueError, IntegrityError) as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400


@bp.post("/partidos/<int:partido_id>/calcular-costos")
def calcular_costos_partido(partido_id):
    """Calcula una cotización sin crear asignaciones ni escribir cambios."""
    datos = request.get_json(silent=True) or {}
    arbitro_id = datos.get("arbitro_id")
    if isinstance(arbitro_id, bool) or not isinstance(arbitro_id, int):
        return jsonify({"error": "El campo 'arbitro_id' es obligatorio."}), 400
    if db.session.get(Partido, partido_id) is None or db.session.get(Arbitro, arbitro_id) is None:
        return jsonify({"error": "El partido o árbitro indicado no existe."}), 404
    try:
        costos = calcular_viaticos_asignacion(
            arbitro_id,
            partido_id,
            datos.get("cantidad_noches", 1),
            datos.get("cantidad_dias", 1),
            datos.get("medio_transporte") or None,
        )
        return jsonify(costos), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/partidos/<int:partido_id>/asignar")
def asignar_arbitro(partido_id):
    datos = request.get_json(silent=True) or {}
    try:
        asignacion = crear_asignacion(partido_id, datos)
        return jsonify(asignacion.to_dict()), 201
    except AsignacionError as error:
        return jsonify({"error": str(error)}), error.status_code


@bp.put("/asignaciones/<int:asignacion_id>/estado")
def actualizar_estado_asignacion(asignacion_id):
    asignacion = db.session.get(AsignacionPartido, asignacion_id)
    if asignacion is None:
        return jsonify({"error": "Asignación no encontrada."}), 404
    datos = request.get_json(silent=True) or {}
    estado_viaje = datos.get("estado_viaje")
    estado_pago = datos.get("estado_pago")
    if estado_viaje is not None and estado_viaje not in ESTADOS_VIAJE:
        return jsonify({"error": "estado_viaje no válido."}), 400
    if estado_pago is not None and estado_pago not in ESTADOS_PAGO:
        return jsonify({"error": "estado_pago no válido."}), 400
    if estado_viaje is None and estado_pago is None:
        return jsonify({"error": "Indique estado_viaje o estado_pago."}), 400
    if estado_viaje is not None:
        if estado_viaje == "Finalizado" and len(asignacion.partido.asignaciones) != ARBITROS_POR_PARTIDO:
            return jsonify({"error": f"El partido debe tener {ARBITROS_POR_PARTIDO} árbitros asignados antes de finalizar la participación."}), 409
        asignacion.estado_viaje = estado_viaje
        fechas = {"En camino": "fecha_salida", "En ciudad": "fecha_llegada_ciudad",
                  "En estadio": "fecha_llegada_estadio", "Finalizado": "fecha_fin_partido"}
        if estado_viaje in fechas:
            setattr(asignacion, fechas[estado_viaje], datetime.utcnow())
        db.session.add(registrar_y_enviar_evento(asignacion, estado_viaje))
    if estado_pago is not None:
        asignacion.estado_pago = estado_pago
        if estado_pago == "Pagado":
            pago = asignacion.pago
            if pago:
                pago.estado, pago.fecha_pago = "Pagado", datetime.utcnow()
            db.session.add(registrar_y_enviar_evento(asignacion, "Pago realizado"))
    db.session.commit()
    return jsonify(asignacion.to_dict()), 200
