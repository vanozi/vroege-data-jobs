from datetime import datetime
from typing import Optional


ANIMAL_RECORD_DEFAULT_PAYLOAD = {
    "printClassification": True,
    "printGeneral": True,
    "printReproduction": True,
    "historicColor": 10526800,
    "cullingColor": 8421504,
    "descending": False,
    "showFarmName": False,
    "useHistoricColor": True,
    "useCullingColor": True,
    "printHealth": True,
    "startPage": 0,
    "printMovements": True,
    "printMilkTestAll": True,
    "showYoungStockAgeInWeeks": False,
    "printCondition": True,
    "printLactation": True,
    "printReproductionAll": True,
    "defaultMilkRecKind": "MilkMeter",
    "printMilkTest": True,
    "groupByHerd": False,
    "isOwner": False,
    "multiHerdLevel": "ActiveHerd",
    "kind": "Default",
    "name": "Default",
    "active": True,
}


def build_herd_registration_payload(
    herd_id: str,
    date: Optional[datetime] = None,
) -> dict:
    """Build the Uniform Agri herd registration request payload."""
    _validate_herd_id(herd_id)

    if date is None:
        date = datetime.now()

    return {
        "date": _format_uniform_date(date),
        **_build_herd_selection(herd_id),
        "personal": True,
        "report": {"pageOrientation": "Default", "textFontSize": 8},
        "kind": "Default",
        "grids": [
            {
                "name": "GridHerdRegistration",
                "columns": [
                    {"index": 0, "name": "Herd", "width": 75, "visible": True},
                    {"index": 1, "name": "VolgNr", "width": 100, "visible": True},
                    {
                        "index": 2,
                        "name": "Number",
                        "width": 100,
                        "visible": True,
                        "columnType": 1,
                    },
                    {
                        "index": 3,
                        "name": "Name",
                        "width": 200,
                        "visible": True,
                        "columnType": 2,
                    },
                    {
                        "index": 4,
                        "name": "Eartag",
                        "width": 150,
                        "visible": True,
                        "sortIndex": 0,
                        "sortOrder": "asc",
                        "columnType": 3,
                    },
                    {
                        "index": 5,
                        "name": "EartagShort",
                        "width": 100,
                        "visible": True,
                        "columnType": 4,
                    },
                    {"index": 6, "name": "Sex", "width": 100, "visible": True},
                    {
                        "index": 7,
                        "name": "BirthDate",
                        "width": 150,
                        "visible": True,
                    },
                    {
                        "index": 8,
                        "name": "HairColor",
                        "width": 100,
                        "visible": True,
                    },
                    {
                        "index": 9,
                        "name": "DamEartag",
                        "width": 100,
                        "visible": True,
                    },
                ],
            }
        ],
        "name": "Default",
        "active": True,
        "links": [
            {
                "rel": "post",
                "href": (
                    f"/restapi/herd/{herd_id}/management/form/herd/"
                    "herdregistration/preset"
                ),
            },
            {
                "rel": "patch",
                "href": (
                    f"/restapi/herd/{herd_id}/management/form/herd/"
                    "herdregistration/preset"
                ),
            },
        ],
    }


def build_animal_actual_payload(herd_id: str) -> dict:
    """Build the Uniform Agri animal actual tab request payload."""
    _validate_herd_id(herd_id)
    return {
        **ANIMAL_RECORD_DEFAULT_PAYLOAD,
        **_build_herd_selection(herd_id),
    }


def build_milk_recordings_payload(herd_id: str) -> dict:
    """Build the Uniform Agri milk recordings request payload."""
    _validate_herd_id(herd_id)
    return {
        **ANIMAL_RECORD_DEFAULT_PAYLOAD,
        "selectedMilkKind": "MilkMeter",
        "showAllDates": False,
        **_build_herd_selection(herd_id),
    }


def _validate_herd_id(herd_id: str) -> None:
    if herd_id:
        return

    raise ValueError("herd_id is required to build a Uniform Agri payload.")


def _build_herd_selection(herd_id: str) -> dict:
    return {
        "herds": [{"id": herd_id}],
        "accessHerds": [herd_id],
    }


def _format_uniform_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT00:00:00.0")
