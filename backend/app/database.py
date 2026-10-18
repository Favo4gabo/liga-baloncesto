"""Configuración de la conexión a base de datos (SQLAlchemy)."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app: Flask) -> SQLAlchemy:
    """Vincula SQLAlchemy a la aplicación Flask dada."""
    db.init_app(app)
    return db


def create_all(app: Flask) -> None:
    """Crea las tablas declaradas en los modelos si no existen."""
    with app.app_context():
        from . import models  # noqa: F401  (registra los modelos)

        db.create_all()


def get_session():
    """Devuelve la sesión activa de SQLAlchemy."""
    return db.session
