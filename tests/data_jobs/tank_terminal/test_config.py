from pathlib import Path

import pytest

from data_jobs.tank_terminal import config as tank_config


def test_load_tank_terminal_config_strips_quotes_and_parses_values(monkeypatch):
    monkeypatch.setenv("TANK_TERMINAL_BASE_URL", '"http://tank.example.test"')
    monkeypatch.setenv("TANK_TERMINAL_USERNAME", '"user"')
    monkeypatch.setenv("TANK_TERMINAL_PASSWORD", '"password"')
    monkeypatch.setenv("TANK_TERMINAL_HEADLESS", "false")
    monkeypatch.setenv("TANK_TERMINAL_DEFAULT_LIMIT", "5")

    config = tank_config.load_tank_terminal_config(Path("missing.env"))

    assert config.base_url == "http://tank.example.test"
    assert config.username == "user"
    assert config.password == "password"
    assert config.headless is False
    assert config.default_limit == 5


def test_load_tank_terminal_config_requires_username(monkeypatch):
    monkeypatch.setenv("TANK_TERMINAL_BASE_URL", "http://tank.example.test")
    monkeypatch.delenv("TANK_TERMINAL_USERNAME", raising=False)
    monkeypatch.setenv("TANK_TERMINAL_PASSWORD", "password")

    with pytest.raises(tank_config.TankTerminalConfigError) as error:
        tank_config.load_tank_terminal_config(Path("missing.env"))

    assert "TANK_TERMINAL_USERNAME" in str(error.value)


def test_load_tank_terminal_config_rejects_base_url_without_protocol(monkeypatch):
    monkeypatch.setenv("TANK_TERMINAL_BASE_URL", "tank.example.test")
    monkeypatch.setenv("TANK_TERMINAL_USERNAME", "user")
    monkeypatch.setenv("TANK_TERMINAL_PASSWORD", "password")

    with pytest.raises(tank_config.TankTerminalConfigError) as error:
        tank_config.load_tank_terminal_config(Path("missing.env"))

    assert "TANK_TERMINAL_BASE_URL must start with http:// or https://" in str(
        error.value
    )
