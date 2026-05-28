"""Tests for dashboard portal configuration."""

import pytest

from dashboard_portal import config


PORTAL_ENV_NAMES = [
    "PORTAL_SECRET_KEY",
    "PORTAL_SESSION_HOURS",
    "PORTAL_ADMIN_USERNAME",
    "PORTAL_ADMIN_PASSWORD_HASH",
    "PORTAL_DEFAULT_USER_PASSWORD",
    "PORTAL_COOKIE_SECURE",
]


@pytest.fixture(autouse=True)
def clear_portal_env(monkeypatch):
    for name in PORTAL_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_dashboard_portal_config_uses_defaults():
    portal_config = config.load_dashboard_portal_config()

    assert portal_config.secret_key == "dev-dashboard-portal-secret"
    assert portal_config.session_hours == 12
    assert portal_config.admin_username == "admin"
    assert portal_config.admin_password_hash == ""
    assert portal_config.default_user_password == "welkom123"
    assert not portal_config.cookie_secure


def test_load_dashboard_portal_config_reads_environment(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "secret")
    monkeypatch.setenv("PORTAL_SESSION_HOURS", "4")
    monkeypatch.setenv("PORTAL_ADMIN_USERNAME", "wouter")
    monkeypatch.setenv("PORTAL_ADMIN_PASSWORD_HASH", "hash")
    monkeypatch.setenv("PORTAL_DEFAULT_USER_PASSWORD", "default")
    monkeypatch.setenv("PORTAL_COOKIE_SECURE", "true")

    portal_config = config.load_dashboard_portal_config()

    assert portal_config.secret_key == "secret"
    assert portal_config.session_hours == 4
    assert portal_config.admin_username == "wouter"
    assert portal_config.admin_password_hash == "hash"
    assert portal_config.default_user_password == "default"
    assert portal_config.cookie_secure


def test_load_dashboard_portal_config_rejects_invalid_session_hours(monkeypatch):
    monkeypatch.setenv("PORTAL_SESSION_HOURS", "invalid")

    with pytest.raises(ValueError, match="PORTAL_SESSION_HOURS"):
        config.load_dashboard_portal_config()


def test_load_dashboard_portal_config_rejects_invalid_cookie_secure(monkeypatch):
    monkeypatch.setenv("PORTAL_COOKIE_SECURE", "maybe")

    with pytest.raises(ValueError, match="PORTAL_COOKIE_SECURE"):
        config.load_dashboard_portal_config()
