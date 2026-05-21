from pathlib import Path

import pytest

from data_jobs.klauwscore import config
from data_jobs.klauwscore.config import KlauwscoreConfigError


FIXTURE_DIR = Path(__file__).parent / "fixtures"
KLAUWSCORE_ENV_NAMES = [
    "KLAUWSCORE_USERNAME",
    "KLAUWSCORE_PASSWORD",
    "KLAUWSCORE_BASE_URL",
    "KLAUWSCORE_LOGIN_PATH",
    "KLAUWSCORE_AGENDA_PATH",
    "KLAUWSCORE_STALLIJST_PATH",
    "KLAUWSCORE_HEADLESS",
    "KLAUWSCORE_DOWNLOAD_ATTEMPTS",
    "KLAUWSCORE_DOWNLOAD_TIMEOUT_MS",
    "KLAUWSCORE_DEFAULT_LIMIT",
]


@pytest.fixture(autouse=True)
def clear_klauwscore_env(monkeypatch):
    for name in KLAUWSCORE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_load_klauwscore_config_raises_clear_error_for_missing_credentials():
    with pytest.raises(KlauwscoreConfigError, match="KLAUWSCORE_USERNAME"):
        config.load_klauwscore_config(
            repo_env_path=FIXTURE_DIR / "missing-root.env",
            klauwscore_env_path=FIXTURE_DIR / "missing-klauwscore.env",
        )


def test_load_klauwscore_config_uses_defaults():
    loaded_config = config.load_klauwscore_config(
        repo_env_path=FIXTURE_DIR / "defaults.env",
        klauwscore_env_path=FIXTURE_DIR / "missing-klauwscore.env",
    )

    assert loaded_config.username == "user"
    assert loaded_config.password == "secret"
    assert loaded_config.base_url == "http://klauwscore.nl"
    assert loaded_config.login_url == "http://klauwscore.nl/login"
    assert loaded_config.agenda_url == "http://klauwscore.nl/veehouder/agenda"
    assert loaded_config.stallijst_url == "http://klauwscore.nl/veepedicure/stallijst"
    assert loaded_config.headless is True
    assert loaded_config.download_attempts == 3
    assert loaded_config.download_timeout_ms == 120_000
    assert loaded_config.default_limit is None


def test_load_klauwscore_config_preserves_existing_env_load_order():
    loaded_config = config.load_klauwscore_config(
        repo_env_path=FIXTURE_DIR / "root.env",
        klauwscore_env_path=FIXTURE_DIR / "klauwscore.env",
    )

    assert loaded_config.username == "job-user"
    assert loaded_config.password == "root-password"
    assert loaded_config.base_url == "https://job.example"
    assert loaded_config.headless is False
    assert loaded_config.download_attempts == 2
    assert loaded_config.download_timeout_ms == 9000
    assert loaded_config.default_limit == 5


def test_load_klauwscore_config_rejects_invalid_numbers():
    with pytest.raises(KlauwscoreConfigError, match="must be an integer"):
        config.load_klauwscore_config(
            repo_env_path=FIXTURE_DIR / "invalid-number.env",
            klauwscore_env_path=FIXTURE_DIR / "missing-klauwscore.env",
        )


def test_load_klauwscore_config_rejects_invalid_booleans():
    with pytest.raises(KlauwscoreConfigError, match="must be a boolean"):
        config.load_klauwscore_config(
            repo_env_path=FIXTURE_DIR / "invalid-boolean.env",
            klauwscore_env_path=FIXTURE_DIR / "missing-klauwscore.env",
        )
