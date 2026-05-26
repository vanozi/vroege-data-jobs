"""Tests for kippen app authentication helpers."""

from werkzeug import security

from kippen_app import auth
from kippen_app.config import KippenAppConfig


def test_verify_credentials_accepts_matching_hash():
    app_config = KippenAppConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash=security.generate_password_hash("correct-password"),
        cookie_secure=False,
    )

    assert auth.verify_credentials("admin", "correct-password", app_config)


def test_verify_credentials_rejects_wrong_password():
    app_config = KippenAppConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash=security.generate_password_hash("correct-password"),
        cookie_secure=False,
    )

    assert not auth.verify_credentials("admin", "wrong-password", app_config)


def test_verify_credentials_rejects_missing_hash():
    app_config = KippenAppConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash="",
        cookie_secure=False,
    )

    assert not auth.verify_credentials("admin", "correct-password", app_config)
