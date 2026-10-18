"""Gestión de cuentas disponible exclusivamente para superadministradores."""

import secrets

from flask import Blueprint, jsonify, request

from ..authz import roles_required, usuario_actual
from ..database import db
from ..models import Usuario
from ..services.auditoria import registrar_cambio

bp = Blueprint("usuarios", __name__)
ROLES_ASIGNABLES = {"admin", "accountant", "viewer"}


def _snapshot(usuario):
    return {"nombre": usuario.nombre, "email": usuario.email, "rol": usuario.rol, "activo": usuario.activo}


@bp.get("")
@roles_required("super_admin")
def listar_usuarios():
    cuentas = Usuario.query.order_by(Usuario.rol, Usuario.nombre).all()
    return jsonify([usuario.to_public_dict() for usuario in cuentas]), 200


@bp.post("")
@roles_required("super_admin")
def crear_usuario():
    datos = request.get_json(silent=True) or {}
    nombre = str(datos.get("nombre", "")).strip()
    email = str(datos.get("email", "")).strip().lower()
    rol = datos.get("rol", "viewer")
    if not nombre or not email or "@" not in email:
        return jsonify({"error": "Nombre y correo válido son obligatorios."}), 400
    if rol not in ROLES_ASIGNABLES:
        return jsonify({"error": "Los superadministradores solo se crean por el comando seguro de inicialización."}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"error": "Ya existe una cuenta con ese correo."}), 409

    temporal = secrets.token_urlsafe(15)
    usuario = Usuario(nombre=nombre, email=email, rol=rol, activo=True, debe_cambiar_password=True)
    usuario.establecer_password(temporal)
    db.session.add(usuario)
    db.session.flush()
    registrar_cambio("usuario", usuario.id, "CREAR", despues=_snapshot(usuario))
    return jsonify({
        "usuario": usuario.to_public_dict(),
        "contrasena_temporal": temporal,
        "mensaje": "Entrega la contraseña temporal por un canal privado. Solo se muestra esta vez.",
    }), 201


@bp.patch("/<int:usuario_id>")
@roles_required("super_admin")
def actualizar_usuario(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        return jsonify({"error": "Usuario no encontrado."}), 404
    datos = request.get_json(silent=True) or {}
    antes = _snapshot(usuario)
    if usuario.rol == "super_admin" and any(campo in datos for campo in ("activo", "rol")):
        return jsonify({"error": "La cuenta propietaria no se puede bloquear ni degradar desde el panel."}), 409
    if "nombre" in datos:
        nombre = str(datos["nombre"]).strip()
        if not nombre:
            return jsonify({"error": "El nombre no puede estar vacío."}), 400
        usuario.nombre = nombre
    if "rol" in datos:
        if datos["rol"] not in ROLES_ASIGNABLES:
            return jsonify({"error": "Rol no permitido."}), 400
        usuario.rol = datos["rol"]
    if "activo" in datos:
        if not isinstance(datos["activo"], bool):
            return jsonify({"error": "activo debe ser booleano."}), 400
        if usuario.id == usuario_actual().id and not datos["activo"]:
            return jsonify({"error": "No puedes bloquear tu propia sesión."}), 409
        usuario.activo = datos["activo"]
    registrar_cambio("usuario", usuario.id, "ACTUALIZAR", antes, _snapshot(usuario))
    return jsonify(usuario.to_public_dict()), 200


@bp.post("/<int:usuario_id>/reset-password")
@roles_required("super_admin")
def reiniciar_password(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        return jsonify({"error": "Usuario no encontrado."}), 404
    temporal = secrets.token_urlsafe(15)
    usuario.establecer_password(temporal)
    usuario.debe_cambiar_password = True
    registrar_cambio("usuario", usuario.id, "RESET_PASSWORD", despues={"debe_cambiar_password": True})
    return jsonify({"contrasena_temporal": temporal, "mensaje": "La contraseña temporal se muestra una sola vez."}), 200

