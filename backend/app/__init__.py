"""Application factory del backend Flask.

Sistema de gestión y logística de árbitros de baloncesto.
"""

import os
import hmac
from datetime import timedelta

import click
from flask import Flask, g, jsonify, render_template, request, session
from flask_cors import CORS
from flask_migrate import Migrate

from .database import db, init_db
from .models import Usuario
from .routes import register_blueprints
from .routes.auth import password_error


def create_app(config: dict | None = None) -> Flask:
    """Crea y configura una instancia de la aplicación Flask."""
    app = Flask(__name__)
    ruta_db_local = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dev.db"))

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", f"sqlite:///{ruta_db_local}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB para subidas Excel
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )

    if config:
        app.config.update(config)

    origins = [item.strip() for item in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins, "supports_credentials": True, "allow_headers": ["Content-Type", "X-CSRF-Token"]}})

    init_db(app)
    Migrate(app, db)  # habilita `flask db init/migrate/upgrade`
    register_blueprints(app)
    # Mientras se genera la primera migración de Alembic, permite iniciar el entorno
    # de desarrollo con el esquema declarado en SQLAlchemy.
    with app.app_context():
        db.create_all()

    @app.before_request
    def require_authenticated_session():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None
        if request.endpoint in {"health", "auth.login", "bot.recibir_webhook"}:
            return None
        usuario_id = session.get("usuario_id")
        usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
        if usuario is None or not usuario.activo:
            session.clear()
            return jsonify({"error": "Sesión requerida o cuenta bloqueada.", "code": "AUTH_REQUIRED"}), 401
        g.current_user = usuario
        if usuario.debe_cambiar_password and request.endpoint not in {"auth.me", "auth.logout", "auth.change_password"}:
            return jsonify({"error": "Debes cambiar tu contraseña temporal antes de continuar.", "code": "PASSWORD_CHANGE_REQUIRED"}), 403
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            esperado = session.get("csrf_token", "")
            recibido = request.headers.get("X-CSRF-Token", "")
            if not esperado or not recibido or not hmac.compare_digest(esperado, recibido):
                return jsonify({"error": "Token CSRF ausente o inválido."}), 403
        return None

    @app.get("/api/health")
    def health():
        """Comprobación básica de estado del servicio."""
        return jsonify({"status": "ok", "service": "arbitros-backend"})

    @app.get("/")
    def index():
        """Interfaz local de inspección sin necesidad de levantar React."""
        return render_template("index.html")

    @app.cli.command("create-superadmin")
    @click.option("--email", prompt=True, help="Correo de uno de los propietarios.")
    @click.option("--name", prompt="Nombre", help="Nombre que aparecerá en la cuenta.")
    def create_superadmin(email, name):
        """Crea una de las dos cuentas propietarias; nunca imprime ni almacena su clave en claro."""
        correo = email.strip().lower()
        if Usuario.query.filter_by(email=correo).first():
            raise click.ClickException("Ya existe una cuenta con ese correo.")
        if Usuario.query.filter_by(rol="super_admin").count() >= 2:
            raise click.ClickException("Ya existen las dos cuentas super_admin permitidas.")
        password = click.prompt("Contraseña inicial (no se mostrará)", hide_input=True, confirmation_prompt=True)
        error = password_error(password)
        if error:
            raise click.ClickException(error)
        usuario = Usuario(nombre=name.strip(), email=correo, rol="super_admin", activo=True, debe_cambiar_password=False)
        usuario.establecer_password(password)
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Cuenta super_admin creada para {correo}. La contraseña se guardó como hash.")

    @app.cli.command("reset-user-password")
    @click.argument("email")
    def reset_user_password(email):
        """Herramienta operativa para recuperar cuentas; la nueva clave se introduce de forma oculta."""
        usuario = Usuario.query.filter_by(email=email.strip().lower()).first()
        if usuario is None:
            raise click.ClickException("No existe una cuenta con ese correo.")
        password = click.prompt("Nueva contraseña (no se mostrará)", hide_input=True, confirmation_prompt=True)
        error = password_error(password)
        if error:
            raise click.ClickException(error)
        usuario.establecer_password(password)
        usuario.debe_cambiar_password = False
        db.session.commit()
        click.echo("Contraseña restablecida; no puede recuperarse en texto plano.")

    return app


app = create_app()
