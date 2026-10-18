"""Registro de blueprints de la API."""

from flask import Flask

from .arbitros import bp as arbitros_bp
from .catalogos import bp as catalogos_bp
from .partidos import bp as partidos_bp
from .upload import bp as upload_bp
from .historial import bp as historial_bp
from .horarios import bp as horarios_bp
from .bot import bp as bot_bp
from .auth import bp as auth_bp
from .usuarios import bp as usuarios_bp
from .finanzas import bp as finanzas_bp

__all__ = ["register_blueprints"]


def register_blueprints(app: Flask) -> Flask:
    """Registra todos los blueprints de la aplicación bajo /api."""
    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(partidos_bp, url_prefix="/api")
    app.register_blueprint(arbitros_bp, url_prefix="/api/arbitros")
    app.register_blueprint(catalogos_bp, url_prefix="/api/catalogos")
    app.register_blueprint(historial_bp, url_prefix="/api")
    app.register_blueprint(horarios_bp, url_prefix="/api/horarios")
    app.register_blueprint(bot_bp, url_prefix="/api/bot")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(usuarios_bp, url_prefix="/api/usuarios")
    app.register_blueprint(finanzas_bp, url_prefix="/api/finanzas")
    return app
