from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID
import logging
import shutil

import pytest

from data_jobs.uniform_agri import config as uniform_config
from data_jobs.uniform_agri.config import UniformAgriConfig
from data_jobs.uniform_agri.scripts import koe_data


ANIMAL_ID = UUID("12345678-1234-5678-1234-567812345678")
SECOND_ANIMAL_ID = UUID("22345678-1234-5678-1234-567812345678")
MILKING_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@dataclass
class FakeKoe:
    animal_id: UUID
    name: str


@dataclass
class FakeDetail:
    animal_id: UUID


@dataclass
class FakeMelking:
    id: UUID


class FakeService:
    def __init__(self, config):
        self.config = config


def test_parse_collection_date_accepts_iso_date():
    assert koe_data.parse_collection_date("2026-05-19") == datetime(2026, 5, 19)


def test_parser_accepts_recommended_options():
    args = koe_data.build_parser().parse_args(
        [
            "--herd-id",
            "override-herd",
            "--date",
            "2026-05-19",
            "--include-details",
            "--include-milkings",
            "--dry-run",
            "--no-continue-on-animal-error",
            "--limit",
            "10",
        ]
    )

    assert args.herd_id == "override-herd"
    assert args.date == "2026-05-19"
    assert args.include_details is True
    assert args.include_milkings is True
    assert args.dry_run is True
    assert args.continue_on_animal_error is False
    assert args.limit == 10


def test_load_uniform_config_uses_default_herd_id_when_env_is_missing(monkeypatch):
    env_dir = Path("config_default_herd_test").resolve()
    env_dir.mkdir(exist_ok=True)
    env_path = env_dir / ".env"

    try:
        env_path.write_text(
            "\n".join(
                [
                    'UNIFORM_BASE_URL="https://uniform.example.test"',
                    'UNIFORM_USERNAME="user"',
                    'UNIFORM_PASSWORD="password"',
                    'UNIFORM_CLIENT_ID="client-id"',
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.delenv("UNIFORM_HERD_ID", raising=False)

        config = uniform_config.load_uniform_config(env_path)

        assert config.herd_id == uniform_config.DEFAULT_HERD_ID
    finally:
        shutil.rmtree(env_dir)


def test_load_uniform_config_strips_raw_env_quotes(monkeypatch):
    monkeypatch.setenv("UNIFORM_BASE_URL", '"https://uniform.example.test"')
    monkeypatch.setenv("UNIFORM_USERNAME", '"user"')
    monkeypatch.setenv("UNIFORM_PASSWORD", '"password"')
    monkeypatch.setenv("UNIFORM_CLIENT_ID", '"client-id"')
    monkeypatch.delenv("UNIFORM_HERD_ID", raising=False)

    config = uniform_config.load_uniform_config()

    assert config.base_url == "https://uniform.example.test"
    assert config.username == "user"
    assert config.password == "password"
    assert config.client_id == "client-id"


def test_load_uniform_config_rejects_base_url_without_protocol(monkeypatch):
    monkeypatch.setenv("UNIFORM_BASE_URL", "uniform.example.test")
    monkeypatch.setenv("UNIFORM_USERNAME", "user")
    monkeypatch.setenv("UNIFORM_PASSWORD", "password")
    monkeypatch.setenv("UNIFORM_CLIENT_ID", "client-id")

    with pytest.raises(uniform_config.UniformAgriConfigError) as error:
        uniform_config.load_uniform_config()

    assert "UNIFORM_BASE_URL must start with http:// or https://" in str(error.value)


def test_run_dry_run_uses_collectors_and_persistence(monkeypatch, capsys):
    calls = []
    koeien = [
        FakeKoe(ANIMAL_ID, "Koe 1"),
        FakeKoe(SECOND_ANIMAL_ID, "Koe 2"),
    ]

    monkeypatch.setattr(koe_data.uniform_config, "load_uniform_config", build_config)
    monkeypatch.setattr(koe_data, "UniformService", FakeService)
    monkeypatch.setattr(
        koe_data.herd_registration,
        "collect_herd_registration",
        lambda service, herd_id, date: FakeResult(records=koeien),
    )
    monkeypatch.setattr(
        koe_data.animal_details,
        "collect_animal_details",
        lambda service, herd_id, selected_koeien, continue_on_animal_error: FakeResult(
            records=[FakeDetail(selected_koeien[0].animal_id)]
        ),
    )
    monkeypatch.setattr(
        koe_data.milk_recordings,
        "collect_milk_recordings",
        lambda service, herd_id, selected_koeien, continue_on_animal_error: FakeResult(
            records=[FakeMelking(MILKING_ID)],
            skipped_count=24,
        ),
    )
    monkeypatch.setattr(
        koe_data.uniform_agri_persistence,
        "save_koeien",
        lambda records, repository, dry_run, logger: (
            calls.append(("save_koeien", len(records), repository, dry_run))
            or len(records)
        ),
    )
    monkeypatch.setattr(
        koe_data.uniform_agri_persistence,
        "save_koe_details",
        lambda records, repository, dry_run, logger: (
            calls.append(("save_koe_details", len(records), repository, dry_run))
            or len(records)
        ),
    )
    monkeypatch.setattr(
        koe_data.uniform_agri_persistence,
        "save_melkingen",
        lambda records, repository, dry_run, logger: (
            calls.append(("save_melkingen", len(records), repository, dry_run))
            or len(records)
        ),
    )
    monkeypatch.setattr(
        koe_data.uniform_agri_persistence,
        "mark_missing_koeien_not_in_current_herd",
        lambda records, repository, dry_run, logger: (
            calls.append(("mark_missing", len(records), repository, dry_run)) or 0
        ),
    )
    monkeypatch.setattr(
        koe_data,
        "build_repositories",
        lambda: calls.append(("build_repositories", 0, None, False)),
    )

    exit_code = koe_data.main(
        [
            "--dry-run",
            "--include-details",
            "--include-milkings",
            "--limit",
            "1",
        ]
    )

    assert exit_code == 0
    assert calls == [
        ("save_koeien", 1, None, True),
        ("mark_missing", 1, None, True),
        ("save_koe_details", 1, None, True),
        ("save_melkingen", 1, None, True),
    ]
    output = capsys.readouterr().out
    assert "dry_run=True" in output
    assert "koeien=1" in output
    assert "saved_koe_details=1" in output
    assert "saved_melkingen=1" in output
    assert "cows_without_melkingingen=24" in output


def build_config():
    return UniformAgriConfig(
        base_url="https://uniform.example.test",
        username="user",
        password="password",
        client_id="client-id",
        herd_id="config-herd-id",
        access_token="token",
    )


class FakeResult:
    def __init__(self, records=None, failures=None, skipped_count=0):
        self.records = records or []
        self.failures = failures or []
        self.skipped_count = skipped_count

    @property
    def failure_count(self):
        return len(self.failures)


def test_log_failures_writes_structured_failure(caplog):
    failure = type(
        "Failure",
        (),
        {
            "stage": "stage",
            "animal_id": "animal-id",
            "animal_name": "Koe",
            "error_message": "failed",
        },
    )()
    logger = logging.getLogger("test_log_failures")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        koe_data.log_failures(logger, [failure])

    assert "Collection failure stage=stage animal_id=animal-id" in caplog.text
