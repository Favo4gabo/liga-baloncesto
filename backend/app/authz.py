"""Decoradores y utilidades de autorización por rol."""

from functools import wraps

from flask import g, jsonify


def roles_required(*roles):
    """Restringe una vista a los roles indicados; login se valida globalmente."""
    permitidos = set(roles)

    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            usuario = getattr(g, "current_user", None)
            if usuario is None:
                return jsonify({"error": "Inicia sesión para continuar."}), 401
            if usuario.rol not in permitidos:
                return jsonify({"error": "No tienes permiso para realizar esta acción."}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorate


def usuario_actual():
    return getattr(g, "current_user", None)
