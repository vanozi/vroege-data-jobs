from datetime import date, datetime
from uuid import UUID
import logging

from database.models.koe import Koe, KoeDetail
from database.models.melking import Melking
from database.persistence import uniform_agri


ANIMAL_ID = UUID("12345678-1234-5678-1234-567812345678")
SECOND_ANIMAL_ID = UUID("22345678-1234-5678-1234-567812345678")
MILKING_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class FakeKoeRepository:
    def __init__(self):
        self.saved_koeien = []
        self.marked_animal_ids = None

    def upsert_koe(self, koe):
        self.saved_koeien.append(koe)

    def mark_all_not_in_herd(self, animal_ids):
        self.marked_animal_ids = animal_ids
        return 3


class FakeKoeDetailRepository:
    def __init__(self):
        self.saved_details = []

    def upsert_koe_detail(self, detail):
        self.saved_details.append(detail)


class FakeMelkingenRepository:
    def __init__(self):
        self.saved_melkingen = []

    def upsert_melking(self, melking):
        self.saved_melkingen.append(melking)


def test_save_koeien_returns_saved_count_and_logs(caplog):
    repository = FakeKoeRepository()
    koeien = [build_koe(ANIMAL_ID), build_koe(SECOND_ANIMAL_ID)]
    logger = logging.getLogger("test_save_koeien")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = uniform_agri.save_koeien(koeien, repository, logger=logger)

    assert saved_count == 2
    assert repository.saved_koeien == koeien
    assert "Saved 2 koeien." in caplog.text


def test_save_koeien_dry_run_returns_count_without_writes(caplog):
    repository = FakeKoeRepository()
    koeien = [build_koe(ANIMAL_ID)]
    logger = logging.getLogger("test_save_koeien_dry_run")

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = uniform_agri.save_koeien(
            koeien,
            repository,
            dry_run=True,
            logger=logger,
        )

    assert saved_count == 1
    assert repository.saved_koeien == []
    assert "Dry run: would save 1 koeien." in caplog.text


def test_save_koe_details_returns_saved_count():
    repository = FakeKoeDetailRepository()
    details = [build_koe_detail(ANIMAL_ID), build_koe_detail(SECOND_ANIMAL_ID)]

    saved_count = uniform_agri.save_koe_details(details, repository)

    assert saved_count == 2
    assert repository.saved_details == details


def test_save_koe_details_dry_run_skips_writes():
    repository = FakeKoeDetailRepository()
    details = [build_koe_detail(ANIMAL_ID)]

    saved_count = uniform_agri.save_koe_details(details, repository, dry_run=True)

    assert saved_count == 1
    assert repository.saved_details == []


def test_save_melkingen_returns_saved_count():
    repository = FakeMelkingenRepository()
    melkingen = [build_melking(MILKING_ID)]

    saved_count = uniform_agri.save_melkingen(melkingen, repository)

    assert saved_count == 1
    assert repository.saved_melkingen == melkingen


def test_save_melkingen_dry_run_skips_writes():
    repository = FakeMelkingenRepository()
    melkingen = [build_melking(MILKING_ID)]

    saved_count = uniform_agri.save_melkingen(melkingen, repository, dry_run=True)

    assert saved_count == 1
    assert repository.saved_melkingen == []


def test_mark_missing_koeien_returns_marked_count():
    repository = FakeKoeRepository()
    animal_ids = [ANIMAL_ID, SECOND_ANIMAL_ID]

    marked_count = uniform_agri.mark_missing_koeien_not_in_current_herd(
        animal_ids,
        repository,
    )

    assert marked_count == 3
    assert repository.marked_animal_ids == animal_ids


def test_mark_missing_koeien_dry_run_skips_repository_call(caplog):
    repository = FakeKoeRepository()
    logger = logging.getLogger("test_mark_missing_koeien_dry_run")

    with caplog.at_level(logging.INFO, logger=logger.name):
        marked_count = uniform_agri.mark_missing_koeien_not_in_current_herd(
            [ANIMAL_ID],
            repository,
            dry_run=True,
            logger=logger,
        )

    assert marked_count == 0
    assert repository.marked_animal_ids is None
    assert (
        "Dry run: would mark koeien outside 1 current animal ids as inactive."
        in caplog.text
    )


def build_koe(animal_id):
    return Koe(
        animalId=animal_id,
        sex="female",
        eartag=f"NL{str(animal_id)[:4]}",
        birthDate=date(2024, 1, 2),
        name="Koe",
        number=101,
        hairColor="black-white",
        eartagShort=str(animal_id)[:4],
    )


def build_koe_detail(animal_id):
    return KoeDetail(
        animalId=animal_id,
        animalType="Cow",
    )


def build_melking(melking_id):
    return Melking(
        id=melking_id,
        animalId=ANIMAL_ID,
        shiftDate=date(2026, 5, 19),
        shiftNumber=1,
        dateTime=datetime(2026, 5, 19, 6, 15),
        dim=120,
        milk=18.5,
        kind=1,
    )
