from datetime import date
import logging
from typing import Optional
from uuid import UUID

import pytest

from database.models.behandeling import KlauwBehandeling
from database.persistence import klauwscore


class FakeKlauwBehandelingenRepository:
    def __init__(self):
        self.saved_items = []

    def upsert_klauw_behandeling(self, item):
        self.saved_items.append(item)


class FakeKoe:
    def __init__(self, animal_id: UUID, eartag: str):
        self.animal_id = animal_id
        self.eartag = eartag


class FakeKoeRepository:
    def __init__(self, koe: Optional[FakeKoe] = None):
        self.koe = koe
        self.calls = []

    def get_by_eartag_short_for_treatment_date(self, eartag_short, behandeldatum):
        self.calls.append((eartag_short, behandeldatum))
        return self.koe


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
            "eartag_short": "101",
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Bekapt",
            "pdf_href": "http://klauwscore.nl/export.pdf",
        },
        {
            "eartag_short": "102",
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Blokje geplaatst",
            "pdf_href": "http://klauwscore.nl/export.pdf",
        },
    ]
    assert "Saved 2 klauw behandelingen." in caplog.text


def test_save_klauw_behandelingen_enriches_with_matching_koe():
    animal_id = UUID("12345678-1234-5678-1234-567812345678")
    repository = FakeKlauwBehandelingenRepository()
    koe_repository = FakeKoeRepository(FakeKoe(animal_id, "NL123456789"))
    rows = [build_row(101, "Bekapt")]

    saved_count = klauwscore.save_klauw_behandelingen(
        rows,
        repository,
        koe_repository,
    )

    assert saved_count == 1
    assert koe_repository.calls == [("101", date(2026, 5, 19))]
    assert repository.saved_items == [
        {
            "eartag_short": "101",
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Bekapt",
            "pdf_href": "http://klauwscore.nl/export.pdf",
            "animal_id": animal_id,
            "eartag": "NL123456789",
        }
    ]


def test_save_klauw_behandelingen_reuses_koe_lookup_for_same_cow_date():
    animal_id = UUID("12345678-1234-5678-1234-567812345678")
    repository = FakeKlauwBehandelingenRepository()
    koe_repository = FakeKoeRepository(FakeKoe(animal_id, "NL123456789"))
    rows = [
        build_row(101, "Bekapt"),
        build_row(101, "Blokje geplaatst"),
    ]

    saved_count = klauwscore.save_klauw_behandelingen(
        rows,
        repository,
        koe_repository,
    )

    assert saved_count == 2
    assert koe_repository.calls == [("101", date(2026, 5, 19))]


def test_save_klauw_behandelingen_logs_periodic_progress(caplog):
    repository = FakeKlauwBehandelingenRepository()
    rows = [build_row(101, "Bekapt"), build_row(102, "Blokje geplaatst")]
    logger = logging.getLogger("test_save_klauw_behandelingen_progress")

    with caplog.at_level(logging.INFO, logger=logger.name):
        klauwscore.save_klauw_behandelingen(
            rows,
            repository,
            logger=logger,
            progress_interval=1,
        )

    assert "Saving klauw behandelingen: 1/2 processed." in caplog.text
    assert "Saving klauw behandelingen: 2/2 processed." in caplog.text


def test_save_klauw_behandelingen_skips_enrichment_without_matching_koe():
    repository = FakeKlauwBehandelingenRepository()
    koe_repository = FakeKoeRepository()
    rows = [build_row(101, "Bekapt")]

    saved_count = klauwscore.save_klauw_behandelingen(
        rows,
        repository,
        koe_repository,
    )

    assert saved_count == 1
    assert repository.saved_items == [
        {
            "eartag_short": "101",
            "behandeldatum": date(2026, 5, 19),
            "notatie": "Bekapt",
            "pdf_href": "http://klauwscore.nl/export.pdf",
        }
    ]


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


def build_row(eartag_short: int, notatie: str) -> dict[str, object]:
    return {
        "eartag_short": str(eartag_short),
        "behandeldatum": date(2026, 5, 19),
        "notatie": notatie,
        "pdf_href": "http://klauwscore.nl/export.pdf",
    }


def build_model(eartag_short: int, notatie: str) -> KlauwBehandeling:
    return KlauwBehandeling(
        eartag_short=str(eartag_short),
        behandeldatum=date(2026, 5, 19),
        notatie=notatie,
    )
