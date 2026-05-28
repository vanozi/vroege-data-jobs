"""Configuration for the dashboard portal."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DashboardPortalConfig:
    """Runtime configuration for the dashboard portal."""

    secret_key: str
    session_hours: int
    admin_username: str
    admin_password_hash: str
    default_user_password: str
    cookie_secure: bool


def load_dashboard_portal_config() -> DashboardPortalConfig:
    """Load dashboard portal configuration from environment variables."""
    return DashboardPortalConfig(
        secret_key=os.getenv("PORTAL_SECRET_KEY", "dev-dashboard-portal-secret"),
        session_hours=_get_int_env("PORTAL_SESSION_HOURS", 12),
        admin_username=os.getenv("PORTAL_ADMIN_USERNAME", "admin"),
        admin_password_hash=os.getenv("PORTAL_ADMIN_PASSWORD_HASH", ""),
        default_user_password=os.getenv("PORTAL_DEFAULT_USER_PASSWORD", "welkom123"),
        cookie_secure=_get_bool_env("PORTAL_COOKIE_SECURE", False),
    )


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized_value = raw_value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean")
