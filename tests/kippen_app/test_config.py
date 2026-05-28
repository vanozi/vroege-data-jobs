"""Tests for kippen app configuration."""

import pytest

from kippen_app import config


KIPPEN_ENV_NAMES = [
    "PORTAL_SECRET_KEY",
    "KIPPEN_APP_SECRET_KEY",
    "KIPPEN_APP_SESSION_HOURS",
    "KIPPEN_APP_ADMIN_USERNAME",
    "KIPPEN_APP_ADMIN_PASSWORD_HASH",
    "KIPPEN_APP_COOKIE_SECURE",
]


@pytest.fixture(autouse=True)
def clear_kippen_env(monkeypatch):
    for name in KIPPEN_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_kippen_app_config_uses_defaults():
    app_config = config.load_kippen_app_config()

    assert app_config.secret_key == "dev-kippen-app-secret"
    assert app_config.session_hours == 12
    assert app_config.admin_username == "admin"
    assert app_config.admin_password_hash == ""
    assert not app_config.cookie_secure


def test_load_kippen_app_config_reads_environment(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "portal-secret")
    monkeypatch.setenv("KIPPEN_APP_SECRET_KEY", "secret")
    monkeypatch.setenv("KIPPEN_APP_SESSION_HOURS", "4")
    monkeypatch.setenv("KIPPEN_APP_ADMIN_USERNAME", "wouter")
    monkeypatch.setenv("KIPPEN_APP_ADMIN_PASSWORD_HASH", "hash")
    monkeypatch.setenv("KIPPEN_APP_COOKIE_SECURE", "true")

    app_config = config.load_kippen_app_config()

    assert app_config.secret_key == "portal-secret"
    assert app_config.session_hours == 4
    assert app_config.admin_username == "wouter"
    assert app_config.admin_password_hash == "hash"
    assert app_config.cookie_secure


def test_load_kippen_app_config_falls_back_to_kippen_secret(monkeypatch):
    monkeypatch.setenv("KIPPEN_APP_SECRET_KEY", "kippen-secret")

    app_config = config.load_kippen_app_config()

    assert app_config.secret_key == "kippen-secret"


def test_load_kippen_app_config_rejects_invalid_session_hours(monkeypatch):
    monkeypatch.setenv("KIPPEN_APP_SESSION_HOURS", "invalid")

    with pytest.raises(ValueError, match="KIPPEN_APP_SESSION_HOURS"):
        config.load_kippen_app_config()


def test_load_kippen_app_config_rejects_invalid_cookie_secure(monkeypatch):
    monkeypatch.setenv("KIPPEN_APP_COOKIE_SECURE", "maybe")

    with pytest.raises(ValueError, match="KIPPEN_APP_COOKIE_SECURE"):
        config.load_kippen_app_config()
