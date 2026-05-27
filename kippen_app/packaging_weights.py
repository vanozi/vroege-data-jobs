"""Form helpers for egg packaging weight configs."""

from datetime import date
from typing import Mapping, Optional

from database.models.laying_hens import EggPackagingWeightConfig
from kippen_app import form_parsing


DEFAULT_EGG_COUNT_PER_PALLET = 10800


def build_packaging_weight_config_from_form(
    form_data: Mapping[str, str],
    *,
    existing_config: Optional[EggPackagingWeightConfig] = None,
) -> tuple[Optional[EggPackagingWeightConfig], dict[str, str], dict[str, str]]:
    """Validate form data and return a packaging weight config model."""
    values = _initial_values(form_data)
    errors: dict[str, str] = {}

    if values["supplier_name"] == "":
        errors["supplier_name"] = "Leverancier is verplicht."

    empty_packaging_weight_kg = form_parsing.parse_decimal(
        values["empty_packaging_weight_kg"],
        field_name="empty_packaging_weight_kg",
        label="Leeggoed gewicht",
        errors=errors,
    )
    egg_count_per_pallet = form_parsing.parse_int(
        values["egg_count_per_pallet"],
        field_name="egg_count_per_pallet",
        label="Aantal eieren per pallet",
        errors=errors,
        minimum=1,
    )
    start_date = form_parsing.parse_date(
        values["start_date"],
        field_name="start_date",
        label="Begindatum",
        errors=errors,
    )
    end_date = form_parsing.parse_date(
        values["end_date"],
        field_name="end_date",
        label="Einddatum",
        errors=errors,
        required=False,
    )

    if start_date is not None and end_date is not None and end_date < start_date:
        errors["end_date"] = "Einddatum kan niet voor begindatum liggen."

    if (
        errors
        or empty_packaging_weight_kg is None
        or egg_count_per_pallet is None
        or start_date is None
    ):
        return None, errors, values

    config = EggPackagingWeightConfig(
        id=existing_config.id if existing_config else None,
        supplier_name=values["supplier_name"],
        empty_packaging_weight_kg=empty_packaging_weight_kg,
        egg_count_per_pallet=egg_count_per_pallet,
        start_date=start_date,
        end_date=end_date,
        notes=values["notes"] or None,
    )
    return config, errors, values


def values_from_config(config: EggPackagingWeightConfig) -> dict[str, str]:
    """Return template-ready form values from a stored packaging config."""
    return {
        "supplier_name": config.supplier_name,
        "empty_packaging_weight_kg": form_parsing.format_decimal(
            config.empty_packaging_weight_kg
        ),
        "egg_count_per_pallet": str(config.egg_count_per_pallet),
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat() if config.end_date else "",
        "notes": config.notes or "",
    }


def default_values(start_date: date) -> dict[str, str]:
    """Return defaults for a new packaging weight config form."""
    return {
        "supplier_name": "",
        "empty_packaging_weight_kg": "0",
        "egg_count_per_pallet": str(DEFAULT_EGG_COUNT_PER_PALLET),
        "start_date": start_date.isoformat(),
        "end_date": "",
        "notes": "",
    }


def _initial_values(form_data: Mapping[str, str]) -> dict[str, str]:
    return {
        "supplier_name": form_data.get("supplier_name", "").strip(),
        "empty_packaging_weight_kg": form_data.get(
            "empty_packaging_weight_kg",
            "0",
        ).strip(),
        "egg_count_per_pallet": form_data.get(
            "egg_count_per_pallet",
            str(DEFAULT_EGG_COUNT_PER_PALLET),
        ).strip(),
        "start_date": form_data.get("start_date", "").strip(),
        "end_date": form_data.get("end_date", "").strip(),
        "notes": form_data.get("notes", "").strip(),
    }
