import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import current_user, login_required
from flask_migrate import upgrade as migrate_upgrade

from config import Config, ProductionConfig
from extensions import csrf, db, login_manager, migrate
from models import User, UserRole
from routes.academic import academic_bp
from routes.auth import auth_bp, role_required
from routes.face import face_bp
from routes.analytics import analytics_bp
from routes.ml import ml_bp
from routes.notifications import notifications_bp
from ml.train_model import train_from_cli
from services.dashboard_service import admin_dashboard, faculty_dashboard, student_dashboard


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        static_url_path="/static",
    )
    if config_class is ProductionConfig:
        config_class.validate()
    app.config.from_object(config_class)
    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(academic_bp)
    app.register_blueprint(face_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(notifications_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_oversized_upload(_error):
        return jsonify({"success": False, "error": "The camera frame is too large."}), 413

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    def friendly_error(message: str, status: int):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": message}), status
        return render_template("error.html", message=message, status=status), status

    @app.errorhandler(403)
    def forbidden(_error):
        return friendly_error("You are not authorized to perform this action.", 403)

    @app.errorhandler(404)
    def not_found(_error):
        return friendly_error("The requested page was not found.", 404)

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return friendly_error("Something went wrong. Please try again.", 500)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    @app.get("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

    @app.get("/healthz")
    def healthcheck():
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:
            return jsonify({"status": "unhealthy"}), 503
        return jsonify({"status": "ok", "database": "ok"})

    @app.get("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == UserRole.ADMIN.value:
            return render_template("dashboard.html", role="admin", dashboard=admin_dashboard())
        if current_user.role == UserRole.FACULTY.value:
            return render_template("dashboard.html", role="faculty", dashboard=faculty_dashboard(current_user))
        return render_template("dashboard.html", role="student", dashboard=student_dashboard(current_user))

    @app.get("/admin")
    @role_required(UserRole.ADMIN.value)
    def admin_area():
        return render_template("dashboard.html", role="admin", dashboard=admin_dashboard())

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create all database tables for local development."""
        with app.app_context():
            db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("upgrade-db")
    def upgrade_db_command() -> None:
        """Apply committed migrations without dropping application data."""
        with app.app_context():
            migrate_upgrade()
        click.echo("Database migrations applied.")

    @app.cli.command("seed-admin")
    @click.option("--email", default=None, help="Admin email address.")
    @click.option("--password", default=None, help="Admin password.")
    def seed_admin_command(email: str | None, password: str | None) -> None:
        """Create the configured admin account if it does not exist."""
        admin_email = (email or os.getenv("ADMIN_EMAIL", "admin@example.com")).strip().lower()
        admin_password = password or os.getenv("ADMIN_PASSWORD")
        if not admin_password:
            raise click.UsageError("Set ADMIN_PASSWORD or pass --password.")
        with app.app_context():
            db.create_all()
            existing_user = db.session.scalar(db.select(User).where(User.email == admin_email))
            if existing_user:
                click.echo(f"User already exists: {admin_email}")
                return
            admin = User(email=admin_email, role=UserRole.ADMIN.value)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
        click.echo(f"Admin created: {admin_email}")

    @app.cli.command("reset-admin")
    def reset_admin_command() -> None:
        """Interactively reset the configured development admin password."""
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
        with app.app_context():
            admin = db.session.scalar(
                db.select(User).where(User.email == admin_email, User.role == UserRole.ADMIN.value)
            )
            if admin is None:
                raise click.ClickException(f"Development admin account not found: {admin_email}")

            password = click.prompt("New admin password", hide_input=True, confirmation_prompt=True)
            if not password:
                raise click.UsageError("Password cannot be empty.")
            admin.set_password(password)
            db.session.commit()
        click.echo(f"Development admin password reset for {admin_email}.")

    @app.cli.command("train-risk-model")
    def train_risk_model_command() -> None:
        """Train and persist the attendance-risk model."""
        metadata = train_from_cli(Path(app.instance_path) / "ml_risk_model.joblib")
        click.echo(f"Risk model trained from {metadata['data_source']} data.")
        click.echo(f"Accuracy: {metadata['evaluation']['accuracy']}")

    return app


app = create_app()