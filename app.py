import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, render_template, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from flask_login import current_user, login_required

from config import Config
from extensions import csrf, db, login_manager, migrate
from models import User, UserRole
from routes.academic import academic_bp
from routes.auth import auth_bp, role_required
from routes.face import face_bp
from routes.analytics import analytics_bp
from routes.ml import ml_bp
from ml.train_model import train_from_cli
from services.dashboard_service import admin_dashboard, faculty_dashboard, student_dashboard


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
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

    @app.errorhandler(RequestEntityTooLarge)
    def handle_oversized_upload(_error):
        return jsonify({"success": False, "error": "The camera frame is too large."}), 413

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    @app.get("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("auth.login"))

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

    @app.cli.command("train-risk-model")
    def train_risk_model_command() -> None:
        """Train and persist the attendance-risk model."""
        metadata = train_from_cli(Path(app.instance_path) / "ml_risk_model.joblib")
        click.echo(f"Risk model trained from {metadata['data_source']} data.")
        click.echo(f"Accuracy: {metadata['evaluation']['accuracy']}")

    return app


app = create_app()