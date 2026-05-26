"""Form helpers for dead hen registrations."""

from datetime import datetime
from typing import Mapping, Optional

from database.models.laying_hens import DeadHenRegistration


STABLE_SIDES = ["Albering kant", "Ziekenboeg kant"]
WALKWAYS = ["Links", "Midden", "Rechts"]
FOUND_PLACES = [
    "In de stelling",
    "Op de stelling",
    "Onder de stelling",
    "In het gangpad",
    "Onbekend",
]


def build_dead_hen_registration_from_form(
    form_data: Mapping[str, str],
    *,
    registered_by: Optional[str],
) -> tuple[Optional[DeadHenRegistration], dict[str, str], dict[str, str]]:
    """Validate form data and return a dead hen registration model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    found_at = _parse_datetime(values["found_at"], errors)
    count = _parse_count(values["count"], errors)
    section_number = _parse_section_number(values["section_number"], errors)
    _validate_choice(values["stable_side"], "stable_side", "Kant", STABLE_SIDES, errors)
    _validate_choice(values["walkway"], "walkway", "Gangpad", WALKWAYS, errors)
    _validate_choice(
        values["found_place"],
        "found_place",
        "Vindplaats",
        FOUND_PLACES,
        errors,
    )

    if errors or found_at is None or section_number is None:
        return None, errors, values

    registration = DeadHenRegistration(
        house_id=values["house_id"] or "main",
        found_at=found_at,
        count=count,
        stable_side=values["stable_side"],
        section_number=section_number,
        walkway=values["walkway"],
        found_place=values["found_place"],
        suspected_cause=values["suspected_cause"] or None,
        observations=values["observations"] or None,
        registered_by=registered_by,
    )
    return registration, errors, values


def default_values(found_at: datetime) -> dict[str, str]:
    """Return defaults for a new dead hen form."""
    return {
        "house_id": "main",
        "found_at": found_at.strftime("%Y-%m-%dT%H:%M"),
        "count": "1",
        "stable_side": STABLE_SIDES[0],
        "section_number": "1",
        "walkway": WALKWAYS[1],
        "found_place": FOUND_PLACES[-1],
        "suspected_cause": "",
        "observations": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "found_at": form_data.get("found_at", "").strip(),
        "count": form_data.get("count", "1").strip(),
        "stable_side": form_data.get("stable_side", "").strip(),
        "section_number": form_data.get("section_number", "").strip(),
        "walkway": form_data.get("walkway", "").strip(),
        "found_place": form_data.get("found_place", "").strip(),
        "suspected_cause": form_data.get("suspected_cause", "").strip(),
        "observations": form_data.get("observations", "").strip(),
    }


def _parse_datetime(
    raw_value: str,
    errors: dict[str, str],
) -> Optional[datetime]:
    if raw_value == "":
        errors["found_at"] = "Datum en tijd zijn verplicht."
        return None

    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        errors["found_at"] = "Datum en tijd zijn ongeldig."
        return None


def _parse_count(raw_value: str, errors: dict[str, str]) -> int:
    try:
        count = int(raw_value)
    except ValueError:
        errors["count"] = "Aantal moet een heel getal zijn."
        return 1

    if count < 1:
        errors["count"] = "Aantal moet minimaal 1 zijn."
        return 1

    return count


def _parse_section_number(
    raw_value: str,
    errors: dict[str, str],
) -> Optional[int]:
    try:
        section_number = int(raw_value)
    except ValueError:
        errors["section_number"] = "Vak moet een getal tussen 1 en 4 zijn."
        return None

    if section_number < 1 or section_number > 4:
        errors["section_number"] = "Vak moet tussen 1 en 4 liggen."
        return None

    return section_number


def _validate_choice(
    value: str,
    field_name: str,
    label: str,
    choices: list[str],
    errors: dict[str, str],
) -> None:
    if value in choices:
        return

    errors[field_name] = f"{label} is ongeldig."
