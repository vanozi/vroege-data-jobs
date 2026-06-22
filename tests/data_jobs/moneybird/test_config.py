from pathlib import Path

import pytest

from data_jobs.moneybird import config as moneybird_config
from data_jobs.moneybird.exceptions import MoneybirdConfigError


def test_load_moneybird_config_strips_quotes_and_parses_values(monkeypatch):
    monkeypatch.setenv("MONEYBIRD_ACCESS_TOKEN", '"secret-token"')
    monkeypatch.setenv("MONEYBIRD_ADMINISTRATION_ID", '"123456"')
    monkeypatch.setenv("MONEYBIRD_ADMINISTRATION_NAME", '"Gebroeders vroege cv"')
    monkeypatch.setenv("MONEYBIRD_BASE_URL", '"https://moneybird.example.test/api"')
    monkeypatch.setenv("MONEYBIRD_TIME_ZONE", "Europe/Amsterdam")
    monkeypatch.setenv("MONEYBIRD_DEFAULT_PERIOD", "this_year")
    monkeypatch.setenv("MONEYBIRD_REQUEST_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("MONEYBIRD_MAX_RETRIES", "4")
    monkeypatch.setenv("MONEYBIRD_RETRY_BACKOFF_SECONDS", "0.5")
    monkeypatch.setenv("MONEYBIRD_SYNC_REPORTS", "true")
    monkeypatch.setenv("MONEYBIRD_SYNC_INVOICES", "false")
    monkeypatch.setenv("MONEYBIRD_SYNC_BANK", "yes")
    monkeypatch.setenv("MONEYBIRD_SYNC_CONTACTS", "0")

    config = moneybird_config.load_moneybird_config(Path("missing.env"))

    assert config.access_token == "secret-token"
    assert config.administration_id == "123456"
    assert config.administration_name == "Gebroeders vroege cv"
    assert config.base_url == "https://moneybird.example.test/api"
    assert config.time_zone == "Europe/Amsterdam"
    assert config.default_period == "this_year"
    assert config.request_timeout_seconds == 15
    assert config.max_retries == 4
    assert config.retry_backoff_seconds == 0.5
    assert config.sync_reports is True
    assert config.sync_invoices is False
    assert config.sync_bank is True
    assert config.sync_contacts is False


def test_load_moneybird_config_defaults_to_internal_dashboard_choices(monkeypatch):
    monkeypatch.setenv("MONEYBIRD_ACCESS_TOKEN", "secret-token")
    monkeypatch.delenv("MONEYBIRD_ADMINISTRATION_ID", raising=False)
    monkeypatch.delenv("MONEYBIRD_ADMINISTRATION_NAME", raising=False)
    monkeypatch.delenv("MONEYBIRD_DEFAULT_PERIOD", raising=False)

    config = moneybird_config.load_moneybird_config(Path("missing.env"))

    assert config.administration_id is None
    assert config.administration_name == "Gebroeders vroege cv"
    assert config.default_period == "this_year"


def test_load_moneybird_config_requires_access_token(monkeypatch):
    monkeypatch.delenv("MONEYBIRD_ACCESS_TOKEN", raising=False)

    with pytest.raises(MoneybirdConfigError) as error:
        moneybird_config.load_moneybird_config(Path("missing.env"))

    assert "MONEYBIRD_ACCESS_TOKEN" in str(error.value)


def test_load_moneybird_config_rejects_invalid_base_url(monkeypatch):
    monkeypatch.setenv("MONEYBIRD_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("MONEYBIRD_BASE_URL", "moneybird.example.test")

    with pytest.raises(MoneybirdConfigError) as error:
        moneybird_config.load_moneybird_config(Path("missing.env"))

    assert "MONEYBIRD_BASE_URL must start with http:// or https://" in str(error.value)


def test_load_moneybird_config_rejects_invalid_retry_count(monkeypatch):
    monkeypatch.setenv("MONEYBIRD_ACCESS_TOKEN", "secret-token")
    monkeypatch.setenv("MONEYBIRD_MAX_RETRIES", "-1")

    with pytest.raises(MoneybirdConfigError) as error:
        moneybird_config.load_moneybird_config(Path("missing.env"))

    assert "MONEYBIRD_MAX_RETRIES must be a non-negative integer" in str(error.value)
