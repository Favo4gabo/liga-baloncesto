"""Rutas de consulta de árbitros y su agenda."""

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..database import db
from ..models import Arbitro, AsignacionPartido, Ciudad, Partido

bp = Blueprint("arbitros", __name__)


@bp.get("/")
def listar_arbitros():
    arbitros = Arbitro.query.order_by(Arbitro.apellido, Arbitro.nombre).all()
    return jsonify([arbitro.to_dict() for arbitro in arbitros]), 200


@bp.post("/")
def crear_arbitro():
    datos = request.get_json(silent=True) or {}
    faltantes = [campo for campo in ("nombre", "apellido", "ciudad_origen_id") if not datos.get(campo)]
    if faltantes:
        return jsonify({"error": "Campos obligatorios: " + ", ".join(faltantes)}), 400
    if db.session.get(Ciudad, datos["ciudad_origen_id"]) is None:
        return jsonify({"error": "La ciudad de origen indicada no existe."}), 400
    try:
        arbitro = Arbitro(nombre=str(datos["nombre"]).strip(), apellido=str(datos["apellido"]).strip(),
                          telefono=datos.get("telefono") or None, email=datos.get("email") or None,
                          activo=datos.get("activo", True), ciudad_origen_id=datos["ciudad_origen_id"])
        db.session.add(arbitro); db.session.commit()
        return jsonify(arbitro.to_dict()), 201
    except (IntegrityError, ValueError) as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400


@bp.get("/<int:arbitro_id>/agenda")
def agenda_arbitro(arbitro_id):
    arbitro = db.session.get(Arbitro, arbitro_id)
    if arbitro is None:
        return jsonify({"error": "Árbitro no encontrado."}), 404
    asignaciones = (
        AsignacionPartido.query.filter_by(arbitro_id=arbitro_id)
        .join(AsignacionPartido.partido)
        .order_by(Partido.fecha_hora)
        .all()
    )
    return jsonify({
        "arbitro": arbitro.to_dict(),
        "asignaciones": [asignacion.to_dict() for asignacion in asignaciones],
    }), 200
