from datetime import datetime
from uuid import UUID

import pytest

from data_jobs.uniform_agri.collectors import (
    animal_details,
    herd_registration,
    milk_recordings,
)
from data_jobs.uniform_agri import transforms


ANIMAL_ID = "12345678-1234-5678-1234-567812345678"
SECOND_ANIMAL_ID = "22345678-1234-5678-1234-567812345678"
HERD_ID = "87654321-4321-8765-4321-876543218765"
MILKING_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class HerdRegistrationService:
    def __init__(self, raw_records):
        self.raw_records = raw_records
        self.calls = []

    def fetch_herd_registration(self, herd_id, date=None):
        self.calls.append((herd_id, date))
        return self.raw_records


class AnimalDetailService:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch_animal_actual(self, herd_id, animal_id):
        self.calls.append((herd_id, animal_id))
        response = self.responses[animal_id]
        if isinstance(response, Exception):
            raise response

        return response


class MilkRecordingService:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def fetch_milk_recordings(self, herd_id, animal_id):
        self.calls.append((herd_id, animal_id))
        response = self.responses[animal_id]
        if isinstance(response, Exception):
            raise response

        return response


def test_collect_herd_registration_skips_excluded_calf_records():
    service = HerdRegistrationService(
        [
            build_registration_raw(name="Koe 1"),
            build_registration_raw(name="VAARSKALF 12", animal_id=SECOND_ANIMAL_ID),
            build_registration_raw(name="STIERKALF 7", animal_id=HERD_ID),
        ]
    )

    result = herd_registration.collect_herd_registration(
        service,
        HERD_ID,
        datetime(2026, 5, 19),
    )

    assert result.record_count == 1
    assert result.failure_count == 0
    assert result.records[0].name == "Koe 1"
    assert service.calls == [(HERD_ID, datetime(2026, 5, 19))]


def test_collect_herd_registration_reports_transform_failures():
    service = HerdRegistrationService(
        [
            build_registration_raw(name="Koe 1"),
            {"animalId": "not-a-uuid", "name": "Broken"},
        ]
    )

    result = herd_registration.collect_herd_registration(service, HERD_ID)

    assert result.record_count == 1
    assert result.failure_count == 1
    assert result.failures[0].animal_id == "not-a-uuid"
    assert result.failures[0].animal_name == "Broken"
    assert result.failures[0].stage == "herd_registration_transform"


def test_collect_herd_registration_can_abort_on_transform_failure():
    service = HerdRegistrationService([{"animalId": "not-a-uuid", "name": "Broken"}])

    with pytest.raises(ValueError):
        herd_registration.collect_herd_registration(
            service,
            HERD_ID,
            continue_on_record_error=False,
        )


def test_collect_animal_details_returns_records_and_failures():
    koeien = [
        transforms.koe_from_registration(build_registration_raw(name="Koe 1")),
        transforms.koe_from_registration(
            build_registration_raw(name="Koe 2", animal_id=SECOND_ANIMAL_ID)
        ),
    ]
    service = AnimalDetailService(
        {
            ANIMAL_ID: build_actual_raw(),
            SECOND_ANIMAL_ID: RuntimeError("detail failed"),
        }
    )

    result = animal_details.collect_animal_details(service, HERD_ID, koeien)

    assert result.record_count == 1
    assert result.failure_count == 1
    assert result.records[0].animal_id == UUID(ANIMAL_ID)
    assert result.failures[0].animal_id == SECOND_ANIMAL_ID
    assert result.failures[0].animal_name == "Koe 2"
    assert result.failures[0].stage == "animal_actual_collection"


def test_collect_animal_details_can_abort_on_animal_failure():
    koeien = [transforms.koe_from_registration(build_registration_raw(name="Koe 1"))]
    service = AnimalDetailService({ANIMAL_ID: RuntimeError("detail failed")})

    with pytest.raises(RuntimeError, match="detail failed"):
        animal_details.collect_animal_details(
            service,
            HERD_ID,
            koeien,
            continue_on_animal_error=False,
        )


def test_collect_milk_recordings_returns_records_and_failures():
    koeien = [
        transforms.koe_from_registration(build_registration_raw(name="Koe 1")),
        transforms.koe_from_registration(
            build_registration_raw(name="Koe 2", animal_id=SECOND_ANIMAL_ID)
        ),
    ]
    service = MilkRecordingService(
        {
            ANIMAL_ID: [build_milking_raw()],
            SECOND_ANIMAL_ID: RuntimeError("milk failed"),
        }
    )

    result = milk_recordings.collect_milk_recordings(service, HERD_ID, koeien)

    assert result.record_count == 1
    assert result.failure_count == 1
    assert result.records[0].id == UUID(MILKING_ID)
    assert result.failures[0].animal_id == SECOND_ANIMAL_ID
    assert result.failures[0].animal_name == "Koe 2"
    assert result.failures[0].stage == "milk_recordings_collection"


def test_collect_milk_recordings_counts_cows_without_recordings():
    koeien = [
        transforms.koe_from_registration(build_registration_raw(name="Koe 1")),
        transforms.koe_from_registration(
            build_registration_raw(name="Koe 2", animal_id=SECOND_ANIMAL_ID)
        ),
    ]
    service = MilkRecordingService(
        {
            ANIMAL_ID: [build_milking_raw()],
            SECOND_ANIMAL_ID: [],
        }
    )

    result = milk_recordings.collect_milk_recordings(service, HERD_ID, koeien)

    assert result.record_count == 1
    assert result.failure_count == 0
    assert result.skipped_count == 1


def test_collect_milk_recordings_can_abort_on_animal_failure():
    koeien = [transforms.koe_from_registration(build_registration_raw(name="Koe 1"))]
    service = MilkRecordingService({ANIMAL_ID: RuntimeError("milk failed")})

    with pytest.raises(RuntimeError, match="milk failed"):
        milk_recordings.collect_milk_recordings(
            service,
            HERD_ID,
            koeien,
            continue_on_animal_error=False,
        )


def test_is_excluded_calf_name_handles_missing_names():
    assert herd_registration.is_excluded_calf_name(None) is False
    assert herd_registration.is_excluded_calf_name("") is False
    assert herd_registration.is_excluded_calf_name("vaarskalf 1") is True
    assert herd_registration.is_excluded_calf_name("stierkalf 1") is True
    assert herd_registration.is_excluded_calf_name("Koe 1") is False


def build_registration_raw(name, animal_id=ANIMAL_ID):
    return {
        "animalId": animal_id,
        "sex": "female",
        "eartag": f"NL{animal_id[:4]}",
        "birthDate": "2024-01-02T00:00:00.0",
        "name": name,
        "number": 101,
        "damEartag": "NL999",
        "hairColor": "black-white",
        "eartagShort": animal_id[:4],
    }


def build_actual_raw():
    return {
        "status": "Lactating",
        "statusDays": 42,
        "daysInMilk": 100,
        "animal": {
            "animalId": ANIMAL_ID,
            "animalType": "Cow",
            "isDead": False,
            "isYoungStock": False,
            "toBeCulled": False,
            "aborted": False,
            "barren": False,
            "isBeef": False,
        },
    }


def build_milking_raw():
    return {
        "id": MILKING_ID,
        "herdId": HERD_ID,
        "animalId": ANIMAL_ID,
        "shiftDate": "2026-05-19T00:00:00.0",
        "shiftNumber": 1,
        "dateTime": "2026-05-19T06:15:00.0",
        "dim": 120,
        "milk": 18.5,
        "kind": 1,
        "condAttnLf": False,
        "condAttnRf": False,
        "condAttnLr": False,
        "condAttnRr": False,
        "indicatieAlternerend": False,
        "canEdit": False,
    }
