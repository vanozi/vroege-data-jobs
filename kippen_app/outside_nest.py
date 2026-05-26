"""Form helpers for outside-nest egg rounds."""

from datetime import datetime
from typing import Mapping, Optional

from database.models.laying_hens import OutsideNestEggRound


def build_outside_nest_round_from_form(
    form_data: Mapping[str, str],
    *,
    registered_by: Optional[str],
) -> tuple[Optional[OutsideNestEggRound], dict[str, str], dict[str, str]]:
    """Validate form data and return an outside-nest egg round model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    round_at = _parse_datetime(values["round_at"], errors)
    egg_count = _parse_egg_count(values["egg_count"], errors)

    if errors or round_at is None:
        return None, errors, values

    egg_round = OutsideNestEggRound(
        house_id=values["house_id"] or "main",
        round_at=round_at,
        egg_count=egg_count,
        notes=values["notes"] or None,
        registered_by=registered_by,
    )
    return egg_round, errors, values


def default_values(round_at: datetime) -> dict[str, str]:
    """Return defaults for a new outside-nest round form."""
    return {
        "house_id": "main",
        "round_at": round_at.strftime("%Y-%m-%dT%H:%M"),
        "egg_count": "0",
        "notes": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "round_at": form_data.get("round_at", "").strip(),
        "egg_count": form_data.get("egg_count", "0").strip(),
        "notes": form_data.get("notes", "").strip(),
    }


def _parse_datetime(
    raw_value: str,
    errors: dict[str, str],
) -> Optional[datetime]:
    if raw_value == "":
        errors["round_at"] = "Datum en tijd zijn verplicht."
        return None

    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        errors["round_at"] = "Datum en tijd zijn ongeldig."
        return None


def _parse_egg_count(raw_value: str, errors: dict[str, str]) -> int:
    try:
        egg_count = int(raw_value)
    except ValueError:
        errors["egg_count"] = "Aantal eieren moet een heel getal zijn."
        return 0

    if egg_count < 0:
        errors["egg_count"] = "Aantal eieren mag niet negatief zijn."
        return 0

    return egg_count
