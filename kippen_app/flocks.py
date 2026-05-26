"""Form helpers for flock management."""

from datetime import date
from typing import Optional

from werkzeug.datastructures import MultiDict

from database.models.laying_hens import Flock


def build_flock_from_form(
    form_data: MultiDict[str, str],
    *,
    existing_flock: Optional[Flock] = None,
) -> tuple[Optional[Flock], dict[str, str], dict[str, str]]:
    """Validate form data and return a flock model."""
    values = {
        "flock_name": form_data.get("flock_name", "").strip(),
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "date_of_birth": form_data.get("date_of_birth", "").strip(),
        "placement_date": form_data.get("placement_date", "").strip(),
        "end_date": form_data.get("end_date", "").strip(),
        "bird_count": form_data.get("bird_count", "").strip(),
        "breed": form_data.get("breed", "").strip(),
        "notes": form_data.get("notes", "").strip(),
    }
    errors: dict[str, str] = {}

    flock_name = values["flock_name"]
    if flock_name == "":
        errors["flock_name"] = "Koppelnaam is verplicht."

    date_of_birth = _parse_date(values["date_of_birth"], "Geboortedatum", errors)
    placement_date = _parse_date(values["placement_date"], "Opzetdatum", errors)
    end_date = _parse_optional_date(values["end_date"], "Einddatum", errors)
    bird_count = _parse_non_negative_int(values["bird_count"], "Aantal hennen", errors)

    if date_of_birth is not None and placement_date is not None:
        if placement_date < date_of_birth:
            errors["placement_date"] = "Opzetdatum kan niet voor geboortedatum liggen."

    if end_date is not None and placement_date is not None:
        if end_date < placement_date:
            errors["end_date"] = "Einddatum kan niet voor opzetdatum liggen."

    if errors:
        return None, errors, values

    flock = Flock(
        id=existing_flock.id if existing_flock is not None else None,
        flock_name=flock_name,
        house_id=values["house_id"],
        date_of_birth=date_of_birth,
        placement_date=placement_date,
        end_date=end_date,
        bird_count=bird_count,
        breed=values["breed"] or None,
        notes=values["notes"] or None,
        is_active=existing_flock.is_active if existing_flock is not None else True,
        archived_at=existing_flock.archived_at if existing_flock is not None else None,
    )
    return flock, {}, values


def values_from_flock(flock: Flock) -> dict[str, str]:
    """Return form-shaped values for an existing flock."""
    return {
        "flock_name": flock.flock_name,
        "house_id": flock.house_id,
        "date_of_birth": flock.date_of_birth.isoformat(),
        "placement_date": flock.placement_date.isoformat(),
        "end_date": flock.end_date.isoformat() if flock.end_date else "",
        "bird_count": str(flock.bird_count),
        "breed": flock.breed or "",
        "notes": flock.notes or "",
    }


def default_values() -> dict[str, str]:
    """Return defaults for a new flock form."""
    today = date.today().isoformat()
    return {
        "flock_name": "",
        "house_id": "main",
        "date_of_birth": today,
        "placement_date": today,
        "end_date": "",
        "bird_count": "",
        "breed": "",
        "notes": "",
    }


def parse_end_date(
    form_data: MultiDict[str, str],
) -> tuple[Optional[date], dict[str, str], str]:
    """Parse the end-date action form."""
    raw_end_date = form_data.get("end_date", "").strip()
    errors: dict[str, str] = {}
    parsed_end_date = _parse_date(raw_end_date, "Einddatum", errors)
    return parsed_end_date, errors, raw_end_date


def _parse_date(
    raw_value: str,
    label: str,
    errors: dict[str, str],
) -> Optional[date]:
    if raw_value == "":
        errors[_field_name(label)] = f"{label} is verplicht."
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        errors[_field_name(label)] = f"{label} is geen geldige datum."
        return None


def _parse_optional_date(
    raw_value: str,
    label: str,
    errors: dict[str, str],
) -> Optional[date]:
    if raw_value == "":
        return None

    return _parse_date(raw_value, label, errors)


def _parse_non_negative_int(
    raw_value: str,
    label: str,
    errors: dict[str, str],
) -> Optional[int]:
    if raw_value == "":
        errors["bird_count"] = f"{label} is verplicht."
        return None

    try:
        value = int(raw_value)
    except ValueError:
        errors["bird_count"] = f"{label} moet een geheel getal zijn."
        return None

    if value < 0:
        errors["bird_count"] = f"{label} mag niet negatief zijn."
        return None

    return value


def _field_name(label: str) -> str:
    return {
        "Geboortedatum": "date_of_birth",
        "Opzetdatum": "placement_date",
        "Einddatum": "end_date",
    }[label]
