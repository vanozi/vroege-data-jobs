from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from database.models.koe import Koe, KoeDetail
from database.models.melking import Melking


def koe_from_registration(raw: dict[str, Any]) -> Koe:
    """Convert one herd registration API item into a Koe model."""
    data = dict(raw)
    data["animalId"] = _parse_uuid(data.get("animalId"))
    data["birthDate"] = _parse_date(data.get("birthDate"))
    return Koe(**data)


def koe_detail_from_actual(raw: dict[str, Any]) -> KoeDetail:
    """Convert an animal actual-tab API response into a KoeDetail model."""
    animal = raw["animal"]
    data = {key: value for key, value in raw.items() if key != "animal"}
    data.update(
        {
            "animalId": _parse_uuid(animal.get("animalId")),
            "previousNumber": animal.get("previousNumber"),
            "transponder1": animal.get("transponder1"),
            "feedingGroupName": animal.get("feedingGroupName"),
            "feedingGroupNumber": animal.get("feedingGroupNumber"),
            "barnGroupName": animal.get("barnGroupName"),
            "barnGroupNumber": animal.get("barnGroupNumber"),
            "animalType": animal.get("animalType"),
            "animalTypeText": animal.get("animalTypeText"),
            "herdName": animal.get("herdName"),
            "lastHerdId": _parse_optional_uuid(animal.get("lastHerdId")),
            "lastCalvingDate": _parse_optional_date(raw.get("lastCalvingDate")),
            "expectedCalvingDate": _parse_optional_date(raw.get("expectedCalvingDate")),
            "expectedDryOffDate": _parse_optional_date(raw.get("expectedDryOffDate")),
            "lastInseminationDate": _parse_optional_date(
                raw.get("lastInseminationDate")
            ),
            "isDead": animal.get("isDead"),
            "isYoungStock": animal.get("isYoungStock"),
            "toBeCulled": animal.get("toBeCulled"),
            "aborted": animal.get("aborted"),
            "barren": animal.get("barren"),
            "isBeef": animal.get("isBeef"),
            "dam": animal.get("dam"),
            "sire": animal.get("sire"),
            "breedText": animal.get("breedText"),
            "age": animal.get("age"),
            "longName": animal.get("longName"),
            "comment": animal.get("comment"),
        }
    )
    return KoeDetail(**data)


def melking_from_recording(raw: dict[str, Any]) -> Melking:
    """Convert one milk recording API item into a Melking model."""
    data = dict(raw)

    for uuid_field in ["id", "herdId", "animalId"]:
        if uuid_field in data:
            data[uuid_field] = _parse_uuid(data[uuid_field])

    if "shiftDate" in data:
        data["shiftDate"] = _parse_date(data["shiftDate"])

    if "dateTime" in data:
        data["dateTime"] = _parse_datetime(data["dateTime"])

    return Melking(**data)


def _parse_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value

    return UUID(str(value))


def _parse_optional_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None

    return _parse_uuid(value)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        normalized_value = value.removesuffix(".0")
        return datetime.fromisoformat(normalized_value)

    raise ValueError(f"Unsupported datetime value: {value!r}")


def _parse_optional_date(value: Any) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        return _parse_datetime(value).date()

    raise ValueError(f"Unsupported date value: {value!r}")


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        return _parse_datetime(value).date()

    raise ValueError(f"Unsupported date value: {value!r}")
