"""Form helpers for egg pallet weight registrations."""

from datetime import date
from typing import Mapping, Optional

from database import laying_hens_calculations
from database.models.laying_hens import EggPackagingWeightConfig
from database.models.laying_hens import EggPalletWeightRegistration
from kippen_app import form_parsing, weekdays


def build_pallet_weight_registration_from_form(
    form_data: Mapping[str, str],
    *,
    packaging_config: Optional[EggPackagingWeightConfig],
    created_by: Optional[str],
    existing_registration: Optional[EggPalletWeightRegistration] = None,
) -> tuple[Optional[EggPalletWeightRegistration], dict[str, str], dict[str, str]]:
    """Validate form data and return a pallet weight registration model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    registration_date = form_parsing.parse_date(
        values["registration_date"],
        field_name="registration_date",
        label="Datum",
        errors=errors,
    )
    packaging_weight_config_id = form_parsing.parse_int(
        values["packaging_weight_config_id"],
        field_name="packaging_weight_config_id",
        label="Leeggoed configuratie",
        errors=errors,
        minimum=1,
    )
    pallet_weight_kg = form_parsing.parse_decimal(
        values["pallet_weight_kg"],
        field_name="pallet_weight_kg",
        label="Palletgewicht",
        errors=errors,
    )

    if packaging_config is None:
        errors["packaging_weight_config_id"] = "Leeggoed configuratie is verplicht."
    elif (
        packaging_weight_config_id is not None
        and packaging_weight_config_id != packaging_config.id
    ):
        errors["packaging_weight_config_id"] = "Leeggoed configuratie is ongeldig."

    if (
        errors
        or registration_date is None
        or packaging_weight_config_id is None
        or pallet_weight_kg is None
        or packaging_config is None
    ):
        return None, errors, values

    try:
        egg_weight_grams = laying_hens_calculations.calculate_egg_weight_grams(
            pallet_weight_kg=pallet_weight_kg,
            empty_packaging_weight_kg=packaging_config.empty_packaging_weight_kg,
            egg_count_per_pallet=packaging_config.egg_count_per_pallet,
        )
    except ValueError as exc:
        errors["pallet_weight_kg"] = str(exc)
        return None, errors, values

    registration = EggPalletWeightRegistration(
        id=existing_registration.id if existing_registration else None,
        house_id=values["house_id"] or "main",
        registration_date=registration_date,
        weekday=weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        packaging_weight_config_id=packaging_config.id,
        supplier_name=packaging_config.supplier_name,
        pallet_weight_kg=pallet_weight_kg,
        empty_packaging_weight_kg=packaging_config.empty_packaging_weight_kg,
        egg_count_per_pallet=packaging_config.egg_count_per_pallet,
        egg_weight_grams=egg_weight_grams,
        notes=values["notes"] or None,
        created_by=created_by,
    )
    values["weekday"] = registration.weekday or ""
    values["supplier_name"] = registration.supplier_name
    values["empty_packaging_weight_kg"] = form_parsing.format_decimal(
        registration.empty_packaging_weight_kg
    )
    values["egg_count_per_pallet"] = str(registration.egg_count_per_pallet)
    values["egg_weight_grams"] = form_parsing.format_decimal(
        registration.egg_weight_grams
    )
    return registration, errors, values


def values_from_registration(
    registration: EggPalletWeightRegistration,
) -> dict[str, str]:
    """Return template-ready form values from a stored pallet registration."""
    return {
        "house_id": registration.house_id,
        "registration_date": registration.registration_date.isoformat(),
        "weekday": registration.weekday or "",
        "packaging_weight_config_id": str(registration.packaging_weight_config_id),
        "supplier_name": registration.supplier_name,
        "pallet_weight_kg": form_parsing.format_decimal(registration.pallet_weight_kg),
        "empty_packaging_weight_kg": form_parsing.format_decimal(
            registration.empty_packaging_weight_kg
        ),
        "egg_count_per_pallet": str(registration.egg_count_per_pallet),
        "egg_weight_grams": form_parsing.format_decimal(registration.egg_weight_grams),
        "notes": registration.notes or "",
    }


def default_values(registration_date: date) -> dict[str, str]:
    """Return defaults for a new pallet weight registration form."""
    return {
        "house_id": "main",
        "registration_date": registration_date.isoformat(),
        "weekday": weekdays.DUTCH_WEEKDAYS[registration_date.weekday()],
        "packaging_weight_config_id": "",
        "supplier_name": "",
        "pallet_weight_kg": "0",
        "empty_packaging_weight_kg": "",
        "egg_count_per_pallet": "",
        "egg_weight_grams": "",
        "notes": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "house_id": form_data.get("house_id", "main").strip() or "main",
        "registration_date": form_data.get("registration_date", "").strip(),
        "weekday": form_data.get("weekday", "").strip(),
        "packaging_weight_config_id": form_data.get(
            "packaging_weight_config_id",
            "",
        ).strip(),
        "supplier_name": form_data.get("supplier_name", "").strip(),
        "pallet_weight_kg": form_data.get("pallet_weight_kg", "0").strip(),
        "empty_packaging_weight_kg": form_data.get(
            "empty_packaging_weight_kg",
            "",
        ).strip(),
        "egg_count_per_pallet": form_data.get("egg_count_per_pallet", "").strip(),
        "egg_weight_grams": form_data.get("egg_weight_grams", "").strip(),
        "notes": form_data.get("notes", "").strip(),
    }
