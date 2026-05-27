"""Form helpers for feed and water registrations."""

from datetime import date
from typing import Mapping, Optional

from database.models.laying_hens import FeedWaterRegistration
from kippen_app import weekdays


def build_feed_water_registration_from_form(
    form_data: Mapping[str, str],
    *,
    created_by: Optional[str],
    existing_registration: Optional[FeedWaterRegistration] = None,
) -> tuple[Optional[FeedWaterRegistration], dict[str, str], dict[str, str]]:
    """Validate form data and return a feed/water registration model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    registration_date = _parse_date(values["registration_date"], errors)
    water_ml = _parse_int(values["water_ml"], "water_ml", "Water", errors)
    feed_grams = _parse_int(values["feed_grams"], "feed_grams", "Voer", errors)

    if errors or registration_date is None:
        return None, errors, values

    registration = FeedWaterRegistration(
        id=existing_registration.id if existing_registration else None,
        house_id=values["house_id"] or "main",
        registration_date=registration_date,
        weekday=weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        water_ml=water_ml,
        feed_grams=feed_grams,
        notes=values["notes"] or None,
        created_by=created_by,
    )
    values["weekday"] = registration.weekday or ""
    return registration, errors, values


def values_from_registration(registration: FeedWaterRegistration) -> dict[str, str]:
    """Return template-ready form values from a stored feed/water registration."""
    return {
        "house_id": registration.house_id,
        "registration_date": registration.registration_date.isoformat(),
        "weekday": registration.weekday or "",
        "water_ml": str(registration.water_ml),
        "feed_grams": str(registration.feed_grams),
        "notes": registration.notes or "",
    }


def default_values(registration_date: date) -> dict[str, str]:
    """Return defaults for a new feed/water registration form."""
    return {
        "house_id": "main",
        "registration_date": registration_date.isoformat(),
        "weekday": weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        "water_ml": "0",
        "feed_grams": "0",
        "notes": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "registration_date": form_data.get("registration_date", "").strip(),
        "weekday": form_data.get("weekday", "").strip(),
        "water_ml": form_data.get("water_ml", "0").strip(),
        "feed_grams": form_data.get("feed_grams", "0").strip(),
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
