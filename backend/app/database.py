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

        dialect = db.engine.dialect
        quote = dialect.identifier_preparer.quote
        timestamp_type = "TIMESTAMP" if dialect.name == "postgresql" else "DATETIME"
        expected_columns = {
            "anulado": "BOOLEAN NOT NULL DEFAULT FALSE",
            "motivo_anulacion": "VARCHAR(300) NULL",
            "anulado_por_id": "INTEGER NULL",
            "anulado_en": f"{timestamp_type} NULL",
        }
        existing_columns = {column["name"] for column in inspector.get_columns("gastos_reales")}
        with db.engine.begin() as connection:
            for name, definition in expected_columns.items():
                if name not in existing_columns:
                    connection.execute(text(
                        f"ALTER TABLE {quote('gastos_reales')} ADD COLUMN {quote(name)} {definition}"
                    ))

        if dialect.name in {"mysql", "mariadb", "postgresql"} and inspector.has_table("usuarios"):
            foreign_keys = inspector.get_foreign_keys("gastos_reales")
            has_annuller_fk = any(fk.get("constrained_columns") == ["anulado_por_id"] for fk in foreign_keys)
            if not has_annuller_fk:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        f"ALTER TABLE {quote('gastos_reales')} ADD CONSTRAINT "
                        f"{quote('fk_gastos_reales_anulado_por')} FOREIGN KEY ({quote('anulado_por_id')}) "
                        f"REFERENCES {quote('usuarios')} ({quote('id')}) ON DELETE SET NULL"
                    ))


def initialize_database(app: Flask) -> None:
    """Initialize schema once safely across the web and Telegram worker services."""
    with app.app_context():
        engine = db.engine
        lock_connection = engine.connect()
        lock_acquired = False
        dialect = engine.dialect.name
        try:
            if dialect == "postgresql":
                lock_connection.execute(text("SELECT pg_advisory_lock(731947201)"))
                lock_connection.commit()
                lock_acquired = True
            elif dialect in {"mysql", "mariadb"}:
                lock_acquired = lock_connection.execute(
                    text("SELECT GET_LOCK('arbiliga_schema_init', 30)")
                ).scalar() == 1
                if not lock_acquired:
                    raise RuntimeError("No se pudo obtener el bloqueo para inicializar el esquema.")

            db.create_all()
            upgrade_legacy_finance_schema(app)
            from .services.catalogos_iniciales import asegurar_catalogo_geografico

            asegurar_catalogo_geografico()
        finally:
            if lock_acquired and dialect == "postgresql":
                lock_connection.execute(text("SELECT pg_advisory_unlock(731947201)"))
                lock_connection.commit()
            elif lock_acquired and dialect in {"mysql", "mariadb"}:
                lock_connection.execute(text("SELECT RELEASE_LOCK('arbiliga_schema_init')"))
            lock_connection.close()


def get_session():
    """Devuelve la sesión activa de SQLAlchemy."""
    return db.session
