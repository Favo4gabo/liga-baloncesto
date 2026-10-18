"""Application factory del backend Flask.

Sistema de gestión y logística de árbitros de baloncesto.
"""

import os

from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_migrate import Migrate

from .database import db, init_db
from .routes import register_blueprints


def create_app(config: dict | None = None) -> Flask:
    """Crea y configura una instancia de la aplicación Flask."""
    app = Flask(__name__)
    ruta_db_local = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dev.db"))

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", f"sqlite:///{ruta_db_local}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB para subidas Excel
    )

    if config:
        app.config.update(config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    init_db(app)
    Migrate(app, db)  # habilita `flask db init/migrate/upgrade`
    register_blueprints(app)
    # Mientras se genera la primera migración de Alembic, permite iniciar el entorno
    # de desarrollo con el esquema declarado en SQLAlchemy.
    with app.app_context():
        db.create_all()

    @app.get("/api/health")
    def health():
        """Comprobación básica de estado del servicio."""
        return jsonify({"status": "ok", "service": "arbitros-backend"})

    @app.get("/")
    def index():
        """Interfaz local de inspección sin necesidad de levantar React."""
        return render_template("index.html")

    return app


app = create_app()
