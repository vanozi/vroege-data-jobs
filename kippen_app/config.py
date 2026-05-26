"""Configuration for the kippen registratie app."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class KippenAppConfig:
    """Runtime configuration for the kippen app."""

    secret_key: str
    session_hours: int
    admin_username: str
    admin_password_hash: str
    cookie_secure: bool


def load_kippen_app_config() -> KippenAppConfig:
    """Load kippen app configuration from environment variables."""
    return KippenAppConfig(
        secret_key=os.getenv("KIPPEN_APP_SECRET_KEY", "dev-kippen-app-secret"),
        session_hours=_get_int_env("KIPPEN_APP_SESSION_HOURS", 12),
        admin_username=os.getenv("KIPPEN_APP_ADMIN_USERNAME", "admin"),
        admin_password_hash=os.getenv("KIPPEN_APP_ADMIN_PASSWORD_HASH", ""),
        cookie_secure=_get_bool_env("KIPPEN_APP_COOKIE_SECURE", False),
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
