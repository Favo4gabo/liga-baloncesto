"""Catálogos operativos de ciudades venezolanas y canchas."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..authz import roles_required
from ..database import db
from ..models import Ciudad, Estado, Partido, UbicacionCancha
from ..services.auditoria import registrar_cambio

bp = Blueprint("catalogos", __name__)


def _coordinate(value, field):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{field} debe ser numérico.") from error


@bp.get("/ciudades")
def listar_ciudades():
    ciudades = Ciudad.query.order_by(Ciudad.nombre).all()
    return jsonify([ciudad.to_dict() for ciudad in ciudades]), 200


@bp.get("/estados")
def listar_estados():
    estados = Estado.query.order_by(Estado.nombre).all()
    return jsonify([estado.to_dict() for estado in estados]), 200


@bp.get("/canchas")
def listar_canchas():
    canchas = UbicacionCancha.query.order_by(UbicacionCancha.nombre_cancha).all()
    return jsonify([cancha.to_dict() | {"ciudad": cancha.ciudad.to_dict()} for cancha in canchas]), 200


@bp.post("/canchas")
@roles_required("super_admin", "admin")
def crear_cancha():
    datos = request.get_json(silent=True) or {}
    faltantes = [campo for campo in ("nombre_cancha", "ciudad_id") if not datos.get(campo)]
    if faltantes:
        return jsonify({"error": "Campos obligatorios: " + ", ".join(faltantes)}), 400
    if db.session.get(Ciudad, datos["ciudad_id"]) is None:
        return jsonify({"error": "La ciudad/estado indicado no existe."}), 400
    try:
        cancha = UbicacionCancha(nombre_cancha=str(datos["nombre_cancha"]).strip(), ciudad_id=datos["ciudad_id"],
                                 direccion=datos.get("direccion") or None, latitud=_coordinate(datos.get("latitud"), "latitud"),
                                 longitud=_coordinate(datos.get("longitud"), "longitud"))
        db.session.add(cancha)
        db.session.flush()
        registrar_cambio("cancha", cancha.id, "CREAR", despues=_snapshot_cancha(cancha))
        return jsonify(cancha.to_dict()), 201
    except (IntegrityError, ValueError) as error:
        db.session.rollback()
        return jsonify({"error": "Ya existe una cancha con ese nombre en la ciudad o los datos son inválidos."}), 400


def _snapshot_cancha(cancha):
    return {
        "nombre_cancha": cancha.nombre_cancha,
        "ciudad_id": cancha.ciudad_id,
        "direccion": cancha.direccion,
        "latitud": str(cancha.latitud) if cancha.latitud is not None else None,
        "longitud": str(cancha.longitud) if cancha.longitud is not None else None,
    }


@bp.put("/canchas/<int:cancha_id>")
@roles_required("super_admin", "admin")
def actualizar_cancha(cancha_id):
    cancha = db.session.get(UbicacionCancha, cancha_id)
    if cancha is None:
        return jsonify({"error": "Cancha no encontrada."}), 404
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not datos:
        return jsonify({"error": "Envía los campos de la cancha que deseas actualizar."}), 400

    antes = _snapshot_cancha(cancha)
    if "nombre_cancha" in datos:
        nombre = datos["nombre_cancha"]
        if not isinstance(nombre, str) or not nombre.strip():
            return jsonify({"error": "nombre_cancha no puede estar vacío."}), 400
        cancha.nombre_cancha = nombre.strip()
    if "ciudad_id" in datos:
        ciudad_id = datos["ciudad_id"]
        if isinstance(ciudad_id, bool) or not isinstance(ciudad_id, int):
            return jsonify({"error": "ciudad_id debe ser un entero."}), 400
        if db.session.get(Ciudad, ciudad_id) is None:
            return jsonify({"error": "La ciudad indicada no existe."}), 400
        cancha.ciudad_id = ciudad_id
    if "direccion" in datos:
        cancha.direccion = str(datos["direccion"]).strip() or None if datos["direccion"] is not None else None
    try:
        if "latitud" in datos:
            cancha.latitud = _coordinate(datos["latitud"], "latitud")
        if "longitud" in datos:
            cancha.longitud = _coordinate(datos["longitud"], "longitud")
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    despues = _snapshot_cancha(cancha)
    try:
        registrar_cambio("cancha", cancha.id, "ACTUALIZAR", antes, despues)
        return jsonify(cancha.to_dict() | {"ciudad": cancha.ciudad.to_dict()}), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Ya existe una cancha con ese nombre en la ciudad seleccionada."}), 409


@bp.delete("/canchas/<int:cancha_id>")
@roles_required("super_admin", "admin")
def eliminar_cancha(cancha_id):
    cancha = db.session.get(UbicacionCancha, cancha_id)
    if cancha is None:
        return jsonify({"error": "Cancha no encontrada."}), 404

    partidos = Partido.query.filter(Partido.estadio_cancha == cancha.nombre_cancha).order_by(Partido.fecha_hora).all()
    if partidos:
        return jsonify({
            "error": "No se puede eliminar la cancha porque está asociada a partidos registrados.",
            "partidos_en_conflicto": [{
                "id": partido.id,
                "fecha_hora": partido.fecha_hora.isoformat(),
                "estadio_cancha": partido.estadio_cancha,
                "ciudad_juego_id": partido.ciudad_juego_id,
                "estado_partido": partido.estado_partido,
            } for partido in partidos],
        }), 409

    antes = _snapshot_cancha(cancha)
    try:
        db.session.delete(cancha)
        db.session.flush()
        registrar_cambio("cancha", cancha_id, "ELIMINAR", antes=antes)
        return jsonify({"mensaje": "Cancha eliminada.", "id": cancha_id}), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "No se pudo eliminar la cancha por una restricción de datos."}), 409
