from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional
from urllib.parse import urljoin

from dotenv import load_dotenv


DEFAULT_BASE_URL = "http://klauwscore.nl"
DEFAULT_LOGIN_PATH = "/login"
DEFAULT_AGENDA_PATH = "/veehouder/agenda"
DEFAULT_DOWNLOAD_ATTEMPTS = 3
DEFAULT_DOWNLOAD_TIMEOUT_MS = 120_000


class KlauwscoreConfigError(RuntimeError):
    """Raised when required Klauwscore configuration is missing or invalid."""


@dataclass(frozen=True)
class KlauwscoreConfig:
    username: str
    password: str
    base_url: str = DEFAULT_BASE_URL
    login_path: str = DEFAULT_LOGIN_PATH
    agenda_path: str = DEFAULT_AGENDA_PATH
    headless: bool = True
    download_attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS
    download_timeout_ms: int = DEFAULT_DOWNLOAD_TIMEOUT_MS
    default_limit: Optional[int] = None

    @property
    def login_url(self) -> str:
        return urljoin(self.base_url, self.login_path)

    @property
    def agenda_url(self) -> str:
        return urljoin(self.base_url, self.agenda_path)


def load_klauwscore_config(
    repo_env_path: Optional[Path] = None,
    klauwscore_env_path: Optional[Path] = None,
) -> KlauwscoreConfig:
    """Load and validate Klauwscore configuration from environment variables."""
    package_root = Path(__file__).resolve().parent
    repo_root = package_root.parents[1]

    if repo_env_path is None:
        repo_env_path = repo_root / ".env"

    if klauwscore_env_path is None:
        klauwscore_env_path = package_root / ".env"

    load_dotenv(dotenv_path=repo_env_path, override=True)
    load_dotenv(dotenv_path=klauwscore_env_path, override=True)

    return KlauwscoreConfig(
        username=_get_required_env("KLAUWSCORE_USERNAME"),
        password=_get_required_env("KLAUWSCORE_PASSWORD"),
        base_url=os.getenv("KLAUWSCORE_BASE_URL", DEFAULT_BASE_URL),
        login_path=os.getenv("KLAUWSCORE_LOGIN_PATH", DEFAULT_LOGIN_PATH),
        agenda_path=os.getenv("KLAUWSCORE_AGENDA_PATH", DEFAULT_AGENDA_PATH),
        headless=_get_bool_env("KLAUWSCORE_HEADLESS", True),
        download_attempts=_get_int_env(
            "KLAUWSCORE_DOWNLOAD_ATTEMPTS",
            DEFAULT_DOWNLOAD_ATTEMPTS,
        ),
        download_timeout_ms=_get_int_env(
            "KLAUWSCORE_DOWNLOAD_TIMEOUT_MS",
            DEFAULT_DOWNLOAD_TIMEOUT_MS,
        ),
        default_limit=_get_optional_int_env("KLAUWSCORE_DEFAULT_LIMIT"),
    )


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value

    raise KlauwscoreConfigError(f"Missing required environment variable: {name}")


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as error:
        raise KlauwscoreConfigError(
            f"Environment variable {name} must be an integer."
        ) from error


def _get_optional_int_env(name: str) -> Optional[int]:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value == "":
        return None

    try:
        return int(raw_value)
    except ValueError as error:
        raise KlauwscoreConfigError(
            f"Environment variable {name} must be an integer."
        ) from error


def _get_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()
    if normalized_value in {"1", "true", "yes", "y", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "n", "off"}:
        return False

    raise KlauwscoreConfigError(f"Environment variable {name} must be a boolean value.")
