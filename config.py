import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'attendance.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    FACE_RECOGNITION_THRESHOLD = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.75"))
    ATTENDANCE_WINDOW_BEFORE_MINUTES = int(os.getenv("ATTENDANCE_WINDOW_BEFORE_MINUTES", "0"))
    ATTENDANCE_WINDOW_AFTER_MINUTES = int(os.getenv("ATTENDANCE_WINDOW_AFTER_MINUTES", "0"))
    ATTENDANCE_LATE_AFTER_MINUTES = int(os.getenv("ATTENDANCE_LATE_AFTER_MINUTES", "10"))
    TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")


class ProductionConfig(Config):
    SECRET_KEY = None
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    WTF_CSRF_ENABLED = True

    @classmethod
    def validate(cls) -> None:
        secret_key = os.getenv("SECRET_KEY")
        database_url = os.getenv("DATABASE_URL")
        if not secret_key or secret_key == "development-only-change-me":
            raise RuntimeError("Production SECRET_KEY must be set to a strong secret.")
        if not database_url:
            raise RuntimeError("Production DATABASE_URL must be configured.")
        cls.SECRET_KEY = secret_key
        cls.SQLALCHEMY_DATABASE_URI = database_url


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
