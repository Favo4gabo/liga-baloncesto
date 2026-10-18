"""Configuración de la conexión a base de datos (SQLAlchemy)."""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

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


def upgrade_legacy_finance_schema(app: Flask) -> None:
    """Add finance-annulment columns to existing databases without losing data.

    ``create_all`` creates missing tables but intentionally does not alter existing
    ones. Earlier ArbiLiga databases have ``gastos_reales`` without the audit
    columns added later, which makes finance summary queries fail when they load
    the relationship.
    """
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table("gastos_reales"):
            return

        expected_columns = {
            "anulado": "BOOLEAN NOT NULL DEFAULT FALSE",
            "motivo_anulacion": "VARCHAR(300) NULL",
            "anulado_por_id": "INTEGER NULL",
            "anulado_en": "DATETIME NULL",
        }
        existing_columns = {column["name"] for column in inspector.get_columns("gastos_reales")}
        with db.engine.begin() as connection:
            for name, definition in expected_columns.items():
                if name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE gastos_reales ADD COLUMN `{name}` {definition}"))

        if db.engine.dialect.name in {"mysql", "mariadb"} and inspector.has_table("usuarios"):
            foreign_keys = inspector.get_foreign_keys("gastos_reales")
            has_annuller_fk = any(fk.get("constrained_columns") == ["anulado_por_id"] for fk in foreign_keys)
            if not has_annuller_fk:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        "ALTER TABLE gastos_reales ADD CONSTRAINT fk_gastos_reales_anulado_por "
                        "FOREIGN KEY (anulado_por_id) REFERENCES usuarios (id) ON DELETE SET NULL"
                    ))


def get_session():
    """Devuelve la sesión activa de SQLAlchemy."""
    return db.session
