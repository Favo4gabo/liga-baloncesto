"""Rutas de consulta de árbitros y su agenda."""

from flask import Blueprint, jsonify

from ..database import db
from ..models import Arbitro, AsignacionPartido, Partido

bp = Blueprint("arbitros", __name__)


@bp.get("/")
def listar_arbitros():
    arbitros = Arbitro.query.order_by(Arbitro.apellido, Arbitro.nombre).all()
    return jsonify([arbitro.to_dict() for arbitro in arbitros]), 200


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
