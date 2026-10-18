"""Inicio/cierre de sesión y cambio de contraseña."""

import secrets

from flask import Blueprint, current_app, g, jsonify, request, session

from ..database import db
from ..models import Usuario

bp = Blueprint("auth", __name__)


def password_error(password):
    if not isinstance(password, str) or len(password) < 6:
        return "La contraseña debe tener al menos 6 caracteres."
    return None


@bp.post("/login")
def login():
    datos = request.get_json(silent=True) or {}
    email = str(datos.get("email", "")).strip().lower()
    password = str(datos.get("password", ""))
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario is None or not usuario.activo or not usuario.verificar_password(password):
        return jsonify({"error": "Correo o contraseña incorrectos."}), 401

    session.clear()
    session.permanent = True
    session["usuario_id"] = usuario.id
    session["csrf_token"] = secrets.token_urlsafe(32)
    current_app.logger.info("Inicio de sesión correcto para user_id=%s", usuario.id)
    return jsonify({"usuario": usuario.to_public_dict(), "csrf_token": session["csrf_token"]}), 200


@bp.get("/me")
def me():
    usuario = g.current_user
    return jsonify({"usuario": usuario.to_public_dict(), "csrf_token": session.get("csrf_token")}), 200


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"mensaje": "Sesión cerrada."}), 200


@bp.post("/change-password")
def change_password():
    usuario = g.current_user
    datos = request.get_json(silent=True) or {}
    nueva = datos.get("new_password", "")
    error = password_error(nueva)
    if error:
        return jsonify({"error": error}), 400
    if not usuario.debe_cambiar_password:
        actual = datos.get("current_password", "")
        if not usuario.verificar_password(actual):
            return jsonify({"error": "La contraseña actual no es correcta."}), 400
    usuario.establecer_password(nueva)
    usuario.debe_cambiar_password = False
    db.session.commit()
    return jsonify({"mensaje": "Contraseña actualizada.", "usuario": usuario.to_public_dict()}), 200
