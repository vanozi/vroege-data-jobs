"""Authentication helpers for the kippen registratie app."""

from werkzeug import security

from kippen_app.config import KippenAppConfig


def verify_credentials(
    username: str,
    password: str,
    app_config: KippenAppConfig,
) -> bool:
    """Return whether username and password match the configured admin user."""
    if not app_config.admin_password_hash:
        return False

    if username != app_config.admin_username:
        return False

    return security.check_password_hash(app_config.admin_password_hash, password)
