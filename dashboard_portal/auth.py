"""Authentication helpers for the dashboard portal."""

from werkzeug import security

from dashboard_portal.config import DashboardPortalConfig


def verify_credentials(
    username: str,
    password: str,
    portal_config: DashboardPortalConfig,
) -> bool:
    """Return whether username and password match the configured admin user."""
    if not portal_config.admin_password_hash:
        return False

    if username != portal_config.admin_username:
        return False

    return security.check_password_hash(portal_config.admin_password_hash, password)
