"""Catálogos operativos de ciudades venezolanas y canchas."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..database import db
from ..models import Ciudad, Estado, UbicacionCancha

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


@bp.post("/ciudades")
def crear_ciudad():
    datos = request.get_json(silent=True) or {}
    if not datos.get("nombre") or not datos.get("estado_id"):
        return jsonify({"error": "nombre y estado_id son obligatorios."}), 400
    if db.session.get(Estado, datos["estado_id"]) is None:
        return jsonify({"error": "El estado indicado no existe."}), 400
    try:
        ciudad = Ciudad(nombre=str(datos["nombre"]).strip(), estado_id=datos["estado_id"])
        db.session.add(ciudad); db.session.commit()
        return jsonify(ciudad.to_dict()), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Ya existe una ciudad con ese nombre en el estado seleccionado."}), 400


@bp.get("/canchas")
def listar_canchas():
    canchas = UbicacionCancha.query.order_by(UbicacionCancha.nombre_cancha).all()
    return jsonify([cancha.to_dict() | {"ciudad": cancha.ciudad.to_dict()} for cancha in canchas]), 200


@bp.post("/canchas")
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
        db.session.add(cancha); db.session.commit()
        return jsonify(cancha.to_dict()), 201
    except (IntegrityError, ValueError) as error:
        db.session.rollback()
        return jsonify({"error": "Ya existe una cancha con ese nombre en la ciudad o los datos son inválidos."}), 400
