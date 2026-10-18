"""Rutas de consulta de árbitros y su agenda."""

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..authz import roles_required
from ..database import db
from ..models import Arbitro, AsignacionPartido, Ciudad, Partido
from ..services.auditoria import registrar_cambio

bp = Blueprint("arbitros", __name__)


@bp.get("/")
def listar_arbitros():
    arbitros = Arbitro.query.order_by(Arbitro.apellido, Arbitro.nombre).all()
    return jsonify([arbitro.to_dict() for arbitro in arbitros]), 200


@bp.post("/")
@roles_required("super_admin", "admin")
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
        db.session.add(arbitro)
        db.session.flush()
        registrar_cambio("arbitro", arbitro.id, "CREAR", despues=_snapshot(arbitro))
        return jsonify(arbitro.to_dict()), 201
    except (IntegrityError, ValueError) as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400


def _snapshot(arbitro):
    return {
        "nombre": arbitro.nombre,
        "apellido": arbitro.apellido,
        "telefono": arbitro.telefono,
        "email": arbitro.email,
        "ciudad_origen_id": arbitro.ciudad_origen_id,
        "activo": arbitro.activo,
    }


@bp.put("/<int:arbitro_id>")
@roles_required("super_admin", "admin")
def actualizar_arbitro(arbitro_id):
    arbitro = db.session.get(Arbitro, arbitro_id)
    if arbitro is None:
        return jsonify({"error": "Árbitro no encontrado."}), 404
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not datos:
        return jsonify({"error": "Envía los campos del árbitro que deseas actualizar."}), 400

    antes = _snapshot(arbitro)
    campos_texto = ("nombre", "apellido", "telefono", "email")
    for campo in campos_texto:
        if campo not in datos:
            continue
        valor = datos[campo]
        if campo in ("nombre", "apellido"):
            if not isinstance(valor, str) or not valor.strip():
                return jsonify({"error": f"{campo} no puede estar vacío."}), 400
            setattr(arbitro, campo, valor.strip())
        else:
            setattr(arbitro, campo, str(valor).strip() or None if valor is not None else None)

    if "ciudad_origen_id" in datos:
        ciudad_id = datos["ciudad_origen_id"]
        if isinstance(ciudad_id, bool) or not isinstance(ciudad_id, int):
            return jsonify({"error": "ciudad_origen_id debe ser un entero."}), 400
        if db.session.get(Ciudad, ciudad_id) is None:
            return jsonify({"error": "La ciudad de origen indicada no existe."}), 400
        arbitro.ciudad_origen_id = ciudad_id

    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            return jsonify({"error": "activo debe ser booleano."}), 400
        arbitro.activo = datos["activo"]

    despues = _snapshot(arbitro)
    accion = (
        "REACTIVAR" if not antes["activo"] and despues["activo"]
        else "DESACTIVAR" if antes["activo"] and not despues["activo"]
        else "ACTUALIZAR"
    )
    try:
        registrar_cambio("arbitro", arbitro.id, accion, antes, despues)
        return jsonify(arbitro.to_dict()), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "No se pudo actualizar el árbitro por una restricción de datos."}), 400


@bp.delete("/<int:arbitro_id>")
@roles_required("super_admin", "admin")
def desactivar_arbitro(arbitro_id):
    arbitro = db.session.get(Arbitro, arbitro_id)
    if arbitro is None:
        return jsonify({"error": "Árbitro no encontrado."}), 404
    if not arbitro.activo:
        return jsonify({"mensaje": "El árbitro ya estaba inactivo.", "arbitro": arbitro.to_dict()}), 200

    antes = _snapshot(arbitro)
    arbitro.activo = False
    despues = _snapshot(arbitro)
    try:
        registrar_cambio("arbitro", arbitro.id, "DESACTIVAR", antes, despues)
        return jsonify({"mensaje": "Árbitro desactivado; el registro y su historial se conservaron.",
                        "arbitro": arbitro.to_dict()}), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "No se pudo desactivar el árbitro."}), 400


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
