"""Form helpers for daily laying registrations."""

from datetime import date
from typing import Mapping, Optional

from database.models.laying_hens import DailyLayingRegistration


DUTCH_WEEKDAYS = [
    "Maandag",
    "Dinsdag",
    "Woensdag",
    "Donderdag",
    "Vrijdag",
    "Zaterdag",
    "Zondag",
]


def build_daily_registration_from_form(
    form_data: Mapping[str, str],
    *,
    created_by: Optional[str],
    existing_registration: Optional[DailyLayingRegistration] = None,
) -> tuple[Optional[DailyLayingRegistration], dict[str, str], dict[str, str]]:
    """Validate form data and return a daily registration model."""
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
    water_liters = _parse_optional_float(
        values["water_liters"],
        "water_liters",
        "Water",
        errors,
    )
    feed_kg = _parse_optional_float(
        values["feed_kg"],
        "feed_kg",
        "Voer",
        errors,
    )

    if errors or registration_date is None:
        return None, errors, values

    total_eggs = first_quality_eggs + second_quality_eggs
    registration = DailyLayingRegistration(
        id=existing_registration.id if existing_registration else None,
        house_id=values["house_id"] or "main",
        registration_date=registration_date,
        weekday=DUTCH_WEEKDAYS[registration_date.weekday()],
        first_quality_eggs=first_quality_eggs,
        second_quality_eggs=second_quality_eggs,
        total_eggs=total_eggs,
        water_liters=water_liters,
        feed_kg=feed_kg,
        notes=values["notes"] or None,
        created_by=created_by,
    )
    values["weekday"] = registration.weekday or ""
    values["total_eggs"] = str(total_eggs)
    return registration, errors, values


def values_from_registration(
    registration: DailyLayingRegistration,
) -> dict[str, str]:
    """Return template-ready form values from a stored registration."""
    return {
        "house_id": registration.house_id,
        "registration_date": registration.registration_date.isoformat(),
        "weekday": registration.weekday or "",
        "first_quality_eggs": str(registration.first_quality_eggs),
        "second_quality_eggs": str(registration.second_quality_eggs),
        "total_eggs": str(registration.total_eggs),
        "water_liters": _optional_number_to_str(registration.water_liters),
        "feed_kg": _optional_number_to_str(registration.feed_kg),
        "notes": registration.notes or "",
    }


def default_values(registration_date: date) -> dict[str, str]:
    """Return defaults for a new daily registration form."""
    return {
        "house_id": "main",
        "registration_date": registration_date.isoformat(),
        "weekday": DUTCH_WEEKDAYS[registration_date.weekday()],
        "first_quality_eggs": "0",
        "second_quality_eggs": "0",
        "total_eggs": "0",
        "water_liters": "",
        "feed_kg": "",
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
        "water_liters": form_data.get("water_liters", "").strip(),
        "feed_kg": form_data.get("feed_kg", "").strip(),
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


def _parse_optional_float(
    raw_value: str,
    field_name: str,
    label: str,
    errors: dict[str, str],
) -> Optional[float]:
    if raw_value == "":
        return None

    try:
        value = float(raw_value.replace(",", "."))
    except ValueError:
        errors[field_name] = f"{label} moet een getal zijn."
        return None

    if value < 0:
        errors[field_name] = f"{label} mag niet negatief zijn."
        return None

    return value


def _optional_number_to_str(value: Optional[float]) -> str:
    if value is None:
        return ""

    return f"{value:.2f}"
