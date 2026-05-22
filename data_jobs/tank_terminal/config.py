"""Configuration for the Tank Terminal datajob."""

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional

from dotenv import load_dotenv


DEFAULT_BASE_URL = "http://82.197.193.195:8080"


class TankTerminalConfigError(RuntimeError):
    """Raised when Tank Terminal configuration is missing or invalid."""


@dataclass(frozen=True)
class TankTerminalConfig:
    """Runtime configuration for Tank Terminal collection."""

    base_url: str
    username: str
    password: str
    headless: bool = True
    default_limit: Optional[int] = None


def load_tank_terminal_config(
    env_path: Optional[Path] = None,
) -> TankTerminalConfig:
    """Load and validate Tank Terminal configuration from environment variables."""
    if env_path is None:
        env_path = Path.cwd() / ".env"

    load_dotenv(dotenv_path=env_path)

    return TankTerminalConfig(
        base_url=_get_url_env("TANK_TERMINAL_BASE_URL", DEFAULT_BASE_URL),
        username=_get_required_env("TANK_TERMINAL_USERNAME"),
        password=_get_required_env("TANK_TERMINAL_PASSWORD"),
        headless=_get_bool_env("TANK_TERMINAL_HEADLESS", True),
        default_limit=_get_optional_int_env("TANK_TERMINAL_DEFAULT_LIMIT"),
    )


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value is not None and value.strip() != "":
        return _clean_env_value(value)

    raise TankTerminalConfigError(f"Missing required environment variable: {name}")


def _get_url_env(name: str, default: str) -> str:
    value = _clean_env_value(os.getenv(name, default))
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")

    raise TankTerminalConfigError(
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

    raise TankTerminalConfigError(f"Environment variable {name} must be a boolean.")


def _get_optional_int_env(name: str) -> Optional[int]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None

    try:
        return int(_clean_env_value(raw_value))
    except ValueError as error:
        raise TankTerminalConfigError(
            f"Environment variable {name} must be an integer."
        ) from error


def _clean_env_value(value: str) -> str:
    cleaned_value = value.strip()
    if len(cleaned_value) >= 2 and cleaned_value[0] == cleaned_value[-1]:
        if cleaned_value[0] in {"'", '"'}:
            return cleaned_value[1:-1]

    return cleaned_value
