"""Configuration for the Moneybird datajob."""

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional

from dotenv import load_dotenv

from data_jobs.moneybird.exceptions import MoneybirdConfigError


DEFAULT_BASE_URL = "https://moneybird.com/api/v2"
DEFAULT_TIME_ZONE = "Europe/Amsterdam"
DEFAULT_PERIOD = "this_year"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0


@dataclass(frozen=True)
class MoneybirdConfig:
    """Runtime configuration for Moneybird collection."""

    access_token: str
    administration_id: Optional[str] = None
    administration_name: str = "Gebroeders vroege cv"
    base_url: str = DEFAULT_BASE_URL
    time_zone: str = DEFAULT_TIME_ZONE
    default_period: str = DEFAULT_PERIOD
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS
    sync_reports: bool = True
    sync_invoices: bool = True
    sync_bank: bool = True
    sync_contacts: bool = True


def load_moneybird_config(env_path: Optional[Path] = None) -> MoneybirdConfig:
    """Load and validate Moneybird configuration from environment variables."""
    if env_path is None:
        env_path = Path.cwd() / ".env"

    load_dotenv(dotenv_path=env_path)

    return MoneybirdConfig(
        access_token=_get_required_env("MONEYBIRD_ACCESS_TOKEN"),
        administration_id=_get_optional_env("MONEYBIRD_ADMINISTRATION_ID"),
        administration_name=_get_env(
            "MONEYBIRD_ADMINISTRATION_NAME",
            "Gebroeders vroege cv",
        ),
        base_url=_get_url_env("MONEYBIRD_BASE_URL", DEFAULT_BASE_URL),
        time_zone=_get_env("MONEYBIRD_TIME_ZONE", DEFAULT_TIME_ZONE),
        default_period=_get_env("MONEYBIRD_DEFAULT_PERIOD", DEFAULT_PERIOD),
        request_timeout_seconds=_get_positive_int_env(
            "MONEYBIRD_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_REQUEST_TIMEOUT_SECONDS,
        ),
        max_retries=_get_non_negative_int_env(
            "MONEYBIRD_MAX_RETRIES",
            DEFAULT_MAX_RETRIES,
        ),
        retry_backoff_seconds=_get_non_negative_float_env(
            "MONEYBIRD_RETRY_BACKOFF_SECONDS",
            DEFAULT_RETRY_BACKOFF_SECONDS,
        ),
        sync_reports=_get_bool_env("MONEYBIRD_SYNC_REPORTS", True),
        sync_invoices=_get_bool_env("MONEYBIRD_SYNC_INVOICES", True),
        sync_bank=_get_bool_env("MONEYBIRD_SYNC_BANK", True),
        sync_contacts=_get_bool_env("MONEYBIRD_SYNC_CONTACTS", True),
    )


def _get_required_env(name: str) -> str:
    value = _get_optional_env(name)
    if value:
        return value

    raise MoneybirdConfigError(f"Missing required environment variable: {name}")


def _get_optional_env(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None

    return _clean_env_value(value)


def _get_env(name: str, default: str) -> str:
    return _get_optional_env(name) or default


def _get_url_env(name: str, default: str) -> str:
    value = _get_env(name, default)
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")

    raise MoneybirdConfigError(
        f"Environment variable {name} must start with http:// or https://."
    )


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized_value = _clean_env_value(raw_value).lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise MoneybirdConfigError(f"Environment variable {name} must be a boolean.")


def _get_positive_int_env(name: str, default: int) -> int:
    value = _get_int_env(name, default)
    if value > 0:
        return value

    raise MoneybirdConfigError(
        f"Environment variable {name} must be a positive integer."
    )


def _get_non_negative_int_env(name: str, default: int) -> int:
    value = _get_int_env(name, default)
    if value >= 0:
        return value

    raise MoneybirdConfigError(
        f"Environment variable {name} must be a non-negative integer."
    )


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        return int(_clean_env_value(raw_value))
    except ValueError as error:
        raise MoneybirdConfigError(
            f"Environment variable {name} must be an integer."
        ) from error


def _get_non_negative_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        value = float(_clean_env_value(raw_value))
    except ValueError as error:
        raise MoneybirdConfigError(
            f"Environment variable {name} must be a number."
        ) from error

    if value >= 0:
        return value

    raise MoneybirdConfigError(f"Environment variable {name} must be non-negative.")


def _clean_env_value(value: str) -> str:
    cleaned_value = value.strip()
    if len(cleaned_value) >= 2 and cleaned_value[0] == cleaned_value[-1]:
        if cleaned_value[0] in {"'", '"'}:
            return cleaned_value[1:-1]

    return cleaned_value
