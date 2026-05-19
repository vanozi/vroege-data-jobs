from copy import deepcopy
from datetime import date, datetime
from uuid import UUID

from data_jobs.uniform_agri import transforms


ANIMAL_ID = "12345678-1234-5678-1234-567812345678"
HERD_ID = "87654321-4321-8765-4321-876543218765"
MILKING_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_koe_from_registration_parses_uuid_and_date_without_mutating_raw():
    raw = {
        "animalId": ANIMAL_ID,
        "sex": "female",
        "eartag": "NL123",
        "birthDate": "2024-01-02T00:00:00.0",
        "name": "Koe 1",
        "number": 101,
        "damEartag": "NL999",
        "hairColor": "black-white",
        "eartagShort": "123",
    }
    original = deepcopy(raw)

    koe = transforms.koe_from_registration(raw)

    assert raw == original
    assert koe.animal_id == UUID(ANIMAL_ID)
    assert koe.birth_date == date(2024, 1, 2)
    assert koe.collar_number == 101


def test_koe_detail_from_actual_extracts_nested_animal_without_mutating_raw():
    raw = {
        "status": "Lactating",
        "statusDays": 42,
        "lastCalvingDate": "2025-07-22T00:00:00.0",
        "expectedCalvingDate": "2026-07-12T00:00:00.0",
        "expectedDryOffDate": "2026-05-24T00:00:00.0",
        "lastInseminationDate": "2025-10-05T00:00:00.0",
        "daysInMilk": 100,
        "animal": {
            "animalId": ANIMAL_ID,
            "previousNumber": 99,
            "transponder1": 123456789,
            "feedingGroupName": "High",
            "feedingGroupNumber": 1,
            "barnGroupName": "Barn",
            "barnGroupNumber": 2,
            "animalType": "Cow",
            "animalTypeText": "Melkkoe",
            "herdName": "Main herd",
            "lastHerdId": HERD_ID,
            "isDead": False,
            "isYoungStock": False,
            "toBeCulled": False,
            "aborted": False,
            "barren": False,
            "isBeef": False,
            "dam": "Dam",
            "sire": "Sire",
            "breedText": "HF",
            "age": "2 years",
            "longName": "Long name",
            "comment": "Comment",
        },
    }
    original = deepcopy(raw)

    detail = transforms.koe_detail_from_actual(raw)

    assert raw == original
    assert detail.animal_id == UUID(ANIMAL_ID)
    assert detail.last_herd_id == UUID(HERD_ID)
    assert detail.animal_type == "Cow"
    assert detail.status == "Lactating"
    assert detail.current_dim == 100
    assert detail.last_calving_date == date(2025, 7, 22)
    assert detail.expected_calving_date == date(2026, 7, 12)
    assert detail.expected_dry_off_date == date(2026, 5, 24)
    assert detail.last_insemination_date == date(2025, 10, 5)


def test_melking_from_recording_parses_ids_and_datetimes_without_mutating_raw():
    raw = {
        "id": MILKING_ID,
        "herdId": HERD_ID,
        "animalId": ANIMAL_ID,
        "shiftDate": "2026-05-19T00:00:00.0",
        "shiftNumber": 1,
        "dateTime": "2026-05-19T06:15:00.0",
        "dim": 120,
        "milk": 18.5,
        "kind": 1,
        "milkSpeed": 2.4,
        "milkDuration": 450,
        "milkStandNo": 12,
        "condAttnLf": False,
        "condAttnRf": False,
        "condAttnLr": False,
        "condAttnRr": False,
        "indicatieAlternerend": False,
        "canEdit": False,
    }
    original = deepcopy(raw)

    melking = transforms.melking_from_recording(raw)

    assert raw == original
    assert melking.id == UUID(MILKING_ID)
    assert melking.animal_id == UUID(ANIMAL_ID)
    assert melking.shift_date == date(2026, 5, 19)
    assert melking.date_time == datetime(2026, 5, 19, 6, 15)
    assert melking.milk == 18.5
