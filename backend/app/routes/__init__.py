"""Registro de blueprints de la API."""

from flask import Flask

from .arbitros import bp as arbitros_bp
from .catalogos import bp as catalogos_bp
from .partidos import bp as partidos_bp
from .upload import bp as upload_bp

__all__ = ["register_blueprints"]


def register_blueprints(app: Flask) -> Flask:
    """Registra todos los blueprints de la aplicación bajo /api."""
    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(partidos_bp, url_prefix="/api")
    app.register_blueprint(arbitros_bp, url_prefix="/api/arbitros")
    app.register_blueprint(catalogos_bp, url_prefix="/api/catalogos")
    return app
