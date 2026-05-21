"""Tests for dashboard portal authentication helpers."""

from werkzeug import security

from dashboard_portal import auth
from dashboard_portal.config import DashboardPortalConfig


def test_verify_credentials_accepts_matching_hash():
    portal_config = DashboardPortalConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash=security.generate_password_hash("correct-password"),
        cookie_secure=False,
    )

    assert auth.verify_credentials("admin", "correct-password", portal_config)


def test_verify_credentials_rejects_wrong_password():
    portal_config = DashboardPortalConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash=security.generate_password_hash("correct-password"),
        cookie_secure=False,
    )

    assert not auth.verify_credentials("admin", "wrong-password", portal_config)


def test_verify_credentials_rejects_missing_hash():
    portal_config = DashboardPortalConfig(
        secret_key="test-secret",
        session_hours=12,
        admin_username="admin",
        admin_password_hash="",
        cookie_secure=False,
    )

    assert not auth.verify_credentials("admin", "correct-password", portal_config)
