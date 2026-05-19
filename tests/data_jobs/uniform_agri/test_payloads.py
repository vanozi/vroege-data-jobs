from datetime import datetime

import pytest

from data_jobs.uniform_agri import payloads


def test_build_herd_registration_payload_uses_supplied_date():
    payload = payloads.build_herd_registration_payload(
        "herd-id",
        datetime(2026, 5, 19, 15, 30),
    )

    assert payload["date"] == "2026-05-19T00:00:00.0"
    assert payload["herds"] == [{"id": "herd-id"}]
    assert payload["accessHerds"] == ["herd-id"]
    assert payload["personal"] is True
    assert "groupByHerd" not in payload
    assert "isOwner" not in payload
    assert "multiHerdLevel" not in payload
    assert "presetLevel" not in payload
    assert "availablePresetLevels" not in payload
    assert payload["grids"][0]["name"] == "GridHerdRegistration"
    assert payload["grids"][0]["columns"][4]["name"] == "Eartag"
    assert payload["links"] == [
        {
            "rel": "post",
            "href": "/restapi/herd/herd-id/management/form/herd/herdregistration/preset",
        },
        {
            "rel": "patch",
            "href": "/restapi/herd/herd-id/management/form/herd/herdregistration/preset",
        },
    ]


def test_build_animal_actual_payload_contains_default_animal_record_options():
    payload = payloads.build_animal_actual_payload("herd-id")

    assert payload["herds"] == [{"id": "herd-id"}]
    assert payload["accessHerds"] == ["herd-id"]
    assert payload["printMilkTest"] is True
    assert payload["defaultMilkRecKind"] == "MilkMeter"
    assert "selectedMilkKind" not in payload


def test_build_milk_recordings_payload_adds_milk_recording_options():
    payload = payloads.build_milk_recordings_payload("herd-id")

    assert payload["herds"] == [{"id": "herd-id"}]
    assert payload["accessHerds"] == ["herd-id"]
    assert payload["selectedMilkKind"] == "MilkMeter"
    assert payload["showAllDates"] is False


def test_animal_payload_builders_return_independent_dicts():
    actual_payload = payloads.build_animal_actual_payload("herd-id")
    milk_payload = payloads.build_milk_recordings_payload("herd-id")

    actual_payload["herds"][0]["id"] = "changed"

    assert milk_payload["herds"] == [{"id": "herd-id"}]
    assert milk_payload["accessHerds"] == ["herd-id"]


@pytest.mark.parametrize(
    "builder",
    [
        payloads.build_herd_registration_payload,
        payloads.build_animal_actual_payload,
        payloads.build_milk_recordings_payload,
    ],
)
def test_payload_builders_require_herd_id(builder):
    with pytest.raises(ValueError, match="herd_id is required"):
        builder("")
