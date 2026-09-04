import pytest

from app import create_app
from config import ProductionConfig, TestConfig


def test_healthcheck_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_production_config_requires_secret_and_database(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProductionConfig)


def test_production_config_can_be_created_with_required_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a-production-secret-that-is-not-default")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///production-test.db")

    application = create_app(ProductionConfig)

    assert application.config["SESSION_COOKIE_SECURE"] is True
    assert application.config["WTF_CSRF_ENABLED"] is True