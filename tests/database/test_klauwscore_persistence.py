from datetime import date
import logging

import pytest

from database.models.behandeling import KlauwBehandeling
from database.persistence import klauwscore


class FakeKlauwBehandelingenRepository:
    def __init__(self):
        self.saved_items = []

    def upsert_klauw_behandeling(self, item):
        self.saved_items.append(item)


def test_save_klauw_behandelingen_returns_saved_count_and_logs(caplog):
    repository = FakeKlauwBehandelingenRepository()
    rows = [build_row(101, "Bekapt"), build_row(102, "Blokje geplaatst")]
    logger = logging.getLogger("test_save_klauw_behandelingen")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = klauwscore.save_klauw_behandelingen(
            rows,
            repository,
            logger=logger,
        )

    assert saved_count == 2
    assert repository.saved_items == [
        {
            "halsbandnummer": 101,
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Bekapt",
        },
        {
            "halsbandnummer": 102,
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Blokje geplaatst",
        },
    ]
    assert "Saved 2 klauw behandelingen." in caplog.text


def test_save_klauw_behandelingen_dry_run_returns_count_without_writes(caplog):
    repository = FakeKlauwBehandelingenRepository()
    rows = [build_row(101, "Bekapt")]
    logger = logging.getLogger("test_save_klauw_behandelingen_dry_run")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = klauwscore.save_klauw_behandelingen(
            rows,
            repository,
            dry_run=True,
            logger=logger,
        )

    assert saved_count == 1
    assert repository.saved_items == []
    assert "Dry run: would save 1 klauw behandelingen." in caplog.text


def test_save_klauw_behandelingen_requires_repository_when_not_dry_run():
    with pytest.raises(ValueError, match="repository is required"):
        klauwscore.save_klauw_behandelingen([build_row(101, "Bekapt")], None)


def test_save_klauw_behandeling_models_returns_saved_count_and_logs(caplog):
    repository = FakeKlauwBehandelingenRepository()
    models = [build_model(101, "Bekapt"), build_model(102, "Blokje geplaatst")]
    logger = logging.getLogger("test_save_klauw_behandeling_models")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = klauwscore.save_klauw_behandeling_models(
            models,
            repository,
            logger=logger,
        )

    assert saved_count == 2
    assert repository.saved_items == models
    assert "Saved 2 klauw behandeling models." in caplog.text


def test_save_klauw_behandeling_models_dry_run_returns_count_without_writes(caplog):
    repository = FakeKlauwBehandelingenRepository()
    models = [build_model(101, "Bekapt")]
    logger = logging.getLogger("test_save_klauw_behandeling_models_dry_run")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = klauwscore.save_klauw_behandeling_models(
            models,
            repository,
            dry_run=True,
            logger=logger,
        )

    assert saved_count == 1
    assert repository.saved_items == []
    assert "Dry run: would save 1 klauw behandeling models." in caplog.text


def test_save_klauw_behandeling_models_requires_repository_when_not_dry_run():
    with pytest.raises(ValueError, match="repository is required"):
        klauwscore.save_klauw_behandeling_models([build_model(101, "Bekapt")], None)


def build_row(halsbandnummer: int, notatie: str) -> dict[str, object]:
    return {
        "halsbandnummer": halsbandnummer,
        "behandeldatum": date(2026, 5, 19),
        "notatie": notatie,
        "pdf_href": "http://klauwscore.nl/export.pdf",
    }


def build_model(halsbandnummer: int, notatie: str) -> KlauwBehandeling:
    return KlauwBehandeling(
        halsbandnummer=halsbandnummer,
        behandeldatum=date(2026, 5, 19),
        notatie=notatie,
    )
