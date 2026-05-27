"""Form helpers for egg registrations."""

from datetime import date
from typing import Mapping, Optional

from database.models.laying_hens import EggRegistration
from kippen_app import weekdays


def build_egg_registration_from_form(
    form_data: Mapping[str, str],
    *,
    created_by: Optional[str],
    existing_registration: Optional[EggRegistration] = None,
) -> tuple[Optional[EggRegistration], dict[str, str], dict[str, str]]:
    """Validate form data and return an egg registration model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    registration_date = _parse_date(values["registration_date"], errors)
    first_quality_eggs = _parse_int(
        values["first_quality_eggs"],
        "first_quality_eggs",
        "1e soort eieren",
        errors,
    )
    second_quality_eggs = _parse_int(
        values["second_quality_eggs"],
        "second_quality_eggs",
        "2e soort eieren",
        errors,
    )

    if errors or registration_date is None:
        return None, errors, values

    total_eggs = first_quality_eggs + second_quality_eggs
    registration = EggRegistration(
        id=existing_registration.id if existing_registration else None,
        house_id=values["house_id"] or "main",
        registration_date=registration_date,
        weekday=weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        first_quality_eggs=first_quality_eggs,
        second_quality_eggs=second_quality_eggs,
        total_eggs=total_eggs,
        notes=values["notes"] or None,
        created_by=created_by,
    )
    values["weekday"] = registration.weekday or ""
    values["total_eggs"] = str(total_eggs)
    return registration, errors, values


def values_from_registration(registration: EggRegistration) -> dict[str, str]:
    """Return template-ready form values from a stored egg registration."""
    return {
        "house_id": registration.house_id,
        "registration_date": registration.registration_date.isoformat(),
        "weekday": registration.weekday or "",
        "first_quality_eggs": str(registration.first_quality_eggs),
        "second_quality_eggs": str(registration.second_quality_eggs),
        "total_eggs": str(registration.total_eggs),
        "notes": registration.notes or "",
    }


def default_values(registration_date: date) -> dict[str, str]:
    """Return defaults for a new egg registration form."""
    return {
        "house_id": "main",
        "registration_date": registration_date.isoformat(),
        "weekday": weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        "first_quality_eggs": "0",
        "second_quality_eggs": "0",
        "total_eggs": "0",
        "notes": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "registration_date": form_data.get("registration_date", "").strip(),
        "weekday": form_data.get("weekday", "").strip(),
        "first_quality_eggs": form_data.get("first_quality_eggs", "0").strip(),
        "second_quality_eggs": form_data.get("second_quality_eggs", "0").strip(),
        "total_eggs": form_data.get("total_eggs", "0").strip(),
        "notes": form_data.get("notes", "").strip(),
    }


def _parse_date(raw_value: str, errors: dict[str, str]) -> Optional[date]:
    if raw_value == "":
        errors["registration_date"] = "Datum is verplicht."
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        errors["registration_date"] = "Datum is ongeldig."
        return None


def _parse_int(
    raw_value: str,
    field_name: str,
    label: str,
    errors: dict[str, str],
) -> int:
    try:
        value = int(raw_value)
    except ValueError:
        errors[field_name] = f"{label} moet een heel getal zijn."
        return 0

    if value < 0:
        errors[field_name] = f"{label} mag niet negatief zijn."
        return 0

    return value
