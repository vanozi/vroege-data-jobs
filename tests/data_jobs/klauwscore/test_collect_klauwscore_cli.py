from datetime import date

import pytest

from data_jobs.klauwscore import collectors
from data_jobs.klauwscore import pdf_parser
from data_jobs.klauwscore.config import KlauwscoreConfig
from data_jobs.klauwscore.scripts import collect_klauwscore
from data_jobs.klauwscore.transforms import DocumentCountMismatch
from data_jobs.klauwscore.transforms import ParsedKlauwscoreDocument


def test_cli_help_works(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["collect_klauwscore", "--help"])

    with pytest.raises(SystemExit) as error:
        collect_klauwscore.main()

    assert error.value.code == 0
    assert "--dry-run" in capsys.readouterr().out


def test_cli_fails_on_missing_config_before_collection(monkeypatch):
    def raise_config_error():
        raise RuntimeError("missing config")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("collector should not run")

    monkeypatch.setattr(
        collect_klauwscore.klauwscore_config,
        "load_klauwscore_config",
        raise_config_error,
    )
    monkeypatch.setattr(
        collect_klauwscore.collectors,
        "collect_klauwscore_rows",
        fail_if_called,
    )
    monkeypatch.setattr("sys.argv", ["collect_klauwscore", "--summary"])

    with pytest.raises(RuntimeError, match="missing config"):
        collect_klauwscore.main()


def test_cli_summary_dry_run_collects_and_does_not_create_repository(
    capsys,
    monkeypatch,
):
    captured = {}

    def fake_save(rows, repository, koe_repository=None, dry_run=False, logger=None):
        captured["rows"] = rows
        captured["repository"] = repository
        captured["koe_repository"] = koe_repository
        captured["dry_run"] = dry_run
        return len(rows)

    monkeypatch.setattr(
        collect_klauwscore.klauwscore_config,
        "load_klauwscore_config",
        build_config,
    )
    monkeypatch.setattr(
        collect_klauwscore.collectors,
        "collect_klauwscore_rows",
        fake_collect_rows,
    )
    monkeypatch.setattr(
        collect_klauwscore.klauwscore_persistence,
        "save_klauw_behandelingen",
        fake_save,
    )
    monkeypatch.setattr("sys.argv", ["collect_klauwscore", "--summary", "--dry-run"])

    collect_klauwscore.main()

    output = capsys.readouterr().out
    assert "source=alle_notaties_pdf" in output
    assert "flat_notitie_rows=2" in output
    assert "deduped_notitie_rows=1" in output
    assert "saved_klauw_behandelingen=1" in output
    assert "dry_run=True" in output
    assert captured["repository"] is None
    assert captured["koe_repository"] is None
    assert captured["dry_run"] is True


def test_cli_flat_persists_deduped_rows_but_outputs_raw_rows(capsys, monkeypatch):
    captured = {}

    class FakeRepository:
        def __init__(self, session_factory):
            captured["session_factory"] = session_factory

    class FakeKoeRepository:
        def __init__(self, session_factory):
            captured["koe_session_factory"] = session_factory

    def fake_save(rows, repository, koe_repository=None, dry_run=False, logger=None):
        captured["rows"] = rows
        captured["repository"] = repository
        captured["koe_repository"] = koe_repository
        captured["dry_run"] = dry_run
        return len(rows)

    monkeypatch.setattr(
        collect_klauwscore.klauwscore_config,
        "load_klauwscore_config",
        build_config,
    )
    monkeypatch.setattr(
        collect_klauwscore.collectors,
        "collect_klauwscore_rows",
        fake_collect_rows,
    )
    monkeypatch.setattr(
        collect_klauwscore,
        "KlauwBehandelingenRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        collect_klauwscore,
        "KoeRepository",
        FakeKoeRepository,
    )
    monkeypatch.setattr(
        collect_klauwscore.klauwscore_persistence,
        "save_klauw_behandelingen",
        fake_save,
    )
    monkeypatch.setattr("sys.argv", ["collect_klauwscore", "--flat"])

    collect_klauwscore.main()

    output = capsys.readouterr().out
    assert '"notatie": "Bekapt"' in output
    assert '"notatie": "Dubbel"' in output
    assert captured["rows"] == [build_row("Bekapt")]
    assert isinstance(captured["repository"], FakeRepository)
    assert isinstance(captured["koe_repository"], FakeKoeRepository)
    assert captured["dry_run"] is False


def test_cli_applies_runtime_overrides(monkeypatch):
    captured = {}

    def fake_collect(config, **kwargs):
        captured["config"] = config
        captured["kwargs"] = kwargs
        return build_result()

    monkeypatch.setattr(
        collect_klauwscore.klauwscore_config,
        "load_klauwscore_config",
        build_config,
    )
    monkeypatch.setattr(
        collect_klauwscore.collectors,
        "collect_klauwscore_rows",
        fake_collect,
    )
    monkeypatch.setattr(
        collect_klauwscore.klauwscore_persistence,
        "save_klauw_behandelingen",
        lambda rows, repository, koe_repository=None, dry_run=False, logger=None: len(
            rows
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_klauwscore",
            "--summary",
            "--limit",
            "7",
            "--no-headless",
            "--download-attempts",
            "4",
            "--download-timeout-ms",
            "9000",
            "--continue-on-document-error",
            "--dry-run",
        ],
    )

    collect_klauwscore.main()

    assert captured["config"].headless is False
    assert captured["config"].download_attempts == 4
    assert captured["config"].download_timeout_ms == 9000
    assert captured["kwargs"]["limit"] == 7
    assert captured["kwargs"]["continue_on_document_error"] is True


def build_config() -> KlauwscoreConfig:
    return KlauwscoreConfig(
        username="user",
        password="secret",
        default_limit=2,
    )


def fake_collect_rows(config, **kwargs):
    return build_result()


def build_result() -> collectors.KlauwscoreCollectionResult:
    record = pdf_parser.KlauwscorePdfRecord(
        behandeldatum=date(2026, 5, 19),
        eartag_short="101",
        notities=["Bekapt", "Dubbel"],
    )
    document = ParsedKlauwscoreDocument(
        behandeldatum=date(2026, 5, 19),
        aantal_koeien=2,
        href="http://klauwscore.nl/export.pdf",
        records=[record],
    )
    return collectors.KlauwscoreCollectionResult(
        documents=[document],
        rows=[build_row("Bekapt"), build_row("Dubbel")],
        deduped_rows=[build_row("Bekapt")],
        count_mismatches=[
            DocumentCountMismatch(
                behandeldatum=date(2026, 5, 19),
                href="http://klauwscore.nl/export.pdf",
                aantal_koeien=2,
                parsed_count=1,
            )
        ],
        failures=[],
    )


def build_row(notatie: str) -> dict[str, object]:
    return {
        "behandeldatum": date(2026, 5, 19),
        "eartag_short": "101",
        "notatie": notatie,
        "pdf_href": "http://klauwscore.nl/export.pdf",
        "aantal_koeien_document": 2,
    }
