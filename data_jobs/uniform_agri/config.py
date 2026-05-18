from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional

from dotenv import load_dotenv


class UniformAgriConfigError(RuntimeError):
    """Raised when required Uniform Agri configuration is missing or invalid."""


@dataclass(frozen=True)
class UniformAgriConfig:
    base_url: str
    username: str
    password: str
    client_id: str
    herd_id: str
    access_token: str = ""
    request_timeout_seconds: int = 60
    max_retries: int = 1


def load_uniform_config(env_path: Optional[Path] = None) -> UniformAgriConfig:
    """Load and validate Uniform Agri configuration from environment variables."""
    if env_path is None:
        env_path = Path.cwd() / ".env"

    load_dotenv(dotenv_path=env_path)

    values = {
        "base_url": _get_required_env("UNIFORM_BASE_URL"),
        "username": _get_required_env("UNIFORM_USERNAME"),
        "password": _get_required_env("UNIFORM_PASSWORD"),
        "client_id": _get_required_env("UNIFORM_CLIENT_ID"),
        "herd_id": _get_required_env("UNIFORM_HERD_ID"),
        "access_token": os.getenv("UNIFORM_ACCESS_TOKEN", ""),
        "request_timeout_seconds": _get_int_env("UNIFORM_REQUEST_TIMEOUT_SECONDS", 60),
        "max_retries": _get_int_env("UNIFORM_MAX_RETRIES", 1),
    }

    return UniformAgriConfig(**values)


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value

    raise UniformAgriConfigError(f"Missing required environment variable: {name}")


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as error:
        raise UniformAgriConfigError(
            f"Environment variable {name} must be an integer."
        ) from error
