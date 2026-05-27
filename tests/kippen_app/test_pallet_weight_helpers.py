"""Tests for egg pallet weight form and calculation helpers."""

from datetime import date
from decimal import Decimal

from database import laying_hens_calculations
from database.models.laying_hens import EggPackagingWeightConfig
from database.models.laying_hens import EggPalletWeightRegistration
from kippen_app import form_parsing, packaging_weights, pallet_weights


def test_parse_decimal_accepts_comma_separator():
    errors: dict[str, str] = {}

    value = form_parsing.parse_decimal(
        "48,500",
        field_name="weight",
        label="Gewicht",
        errors=errors,
    )

    assert value == Decimal("48.500")
    assert errors == {}


def test_parse_decimal_rejects_negative_value():
    errors: dict[str, str] = {}

    value = form_parsing.parse_decimal(
        "-1",
        field_name="weight",
        label="Gewicht",
        errors=errors,
    )

    assert value is None
    assert errors["weight"] == "Gewicht mag niet negatief zijn."


def test_calculate_egg_weight_grams_rounds_to_four_decimals():
    value = laying_hens_calculations.calculate_egg_weight_grams(
        pallet_weight_kg=Decimal("700.000"),
        empty_packaging_weight_kg=Decimal("48.500"),
        egg_count_per_pallet=10800,
    )

    assert value == Decimal("60.3241")


def test_calculate_egg_weight_grams_rejects_invalid_weights():
    try:
        laying_hens_calculations.calculate_egg_weight_grams(
            pallet_weight_kg=Decimal("40.000"),
            empty_packaging_weight_kg=Decimal("48.500"),
            egg_count_per_pallet=10800,
        )
    except ValueError as exc:
        assert "Pallet weight" in str(exc)
    else:
        raise AssertionError("Expected invalid weights to be rejected.")


def test_packaging_weight_form_builds_config_with_decimal_values():
    config, errors, values = packaging_weights.build_packaging_weight_config_from_form(
        {
            "supplier_name": "Eierhandel A",
            "empty_packaging_weight_kg": "48,5",
            "egg_count_per_pallet": "10800",
            "start_date": "2026-05-01",
            "end_date": "",
            "notes": "Standaard pallet",
        }
    )

    assert errors == {}
    assert values["empty_packaging_weight_kg"] == "48,5"
    assert config.supplier_name == "Eierhandel A"
    assert config.empty_packaging_weight_kg == Decimal("48.5")
    assert config.egg_count_per_pallet == 10800
    assert config.start_date == date(2026, 5, 1)
    assert config.end_date is None
    assert config.notes == "Standaard pallet"


def test_packaging_weight_form_validates_required_and_date_order():
    config, errors, _ = packaging_weights.build_packaging_weight_config_from_form(
        {
            "supplier_name": "",
            "empty_packaging_weight_kg": "-1",
            "egg_count_per_pallet": "0",
            "start_date": "2026-06-01",
            "end_date": "2026-05-01",
        }
    )

    assert config is None
    assert errors["supplier_name"] == "Leverancier is verplicht."
    assert errors["empty_packaging_weight_kg"] == (
        "Leeggoed gewicht mag niet negatief zijn."
    )
    assert errors["egg_count_per_pallet"] == (
        "Aantal eieren per pallet moet minimaal 1 zijn."
    )
    assert errors["end_date"] == "Einddatum kan niet voor begindatum liggen."


def test_packaging_weight_values_from_config_formats_decimals():
    values = packaging_weights.values_from_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            egg_count_per_pallet=10800,
            start_date=date(2026, 5, 1),
        )
    )

    assert values["empty_packaging_weight_kg"] == "48.500"
    assert values["egg_count_per_pallet"] == "10800"
    assert values["start_date"] == "2026-05-01"


def test_pallet_weight_form_builds_registration_from_packaging_config():
    config = _packaging_config()

    registration, errors, values = (
        pallet_weights.build_pallet_weight_registration_from_form(
            {
                "registration_date": "2026-05-26",
                "packaging_weight_config_id": str(config.id),
                "pallet_weight_kg": "700,000",
                "notes": "Pallet 1",
            },
            packaging_config=config,
            created_by="admin",
        )
    )

    assert errors == {}
    assert values["supplier_name"] == "Eierhandel A"
    assert values["egg_weight_grams"] == "60.3241"
    assert registration.registration_date == date(2026, 5, 26)
    assert registration.weekday == "Dinsdag"
    assert registration.packaging_weight_config_id == config.id
    assert registration.supplier_name == "Eierhandel A"
    assert registration.empty_packaging_weight_kg == Decimal("48.500")
    assert registration.egg_count_per_pallet == 10800
    assert registration.egg_weight_grams == Decimal("60.3241")
    assert registration.created_by == "admin"


def test_pallet_weight_form_requires_packaging_config():
    registration, errors, _ = pallet_weights.build_pallet_weight_registration_from_form(
        {
            "registration_date": "2026-05-26",
            "packaging_weight_config_id": "",
            "pallet_weight_kg": "700",
        },
        packaging_config=None,
        created_by="admin",
    )

    assert registration is None
    assert errors["packaging_weight_config_id"] == (
        "Leeggoed configuratie is verplicht."
    )


def test_pallet_weight_form_rejects_pallet_below_empty_packaging():
    config = _packaging_config()

    registration, errors, _ = pallet_weights.build_pallet_weight_registration_from_form(
        {
            "registration_date": "2026-05-26",
            "packaging_weight_config_id": str(config.id),
            "pallet_weight_kg": "40",
        },
        packaging_config=config,
        created_by="admin",
    )

    assert registration is None
    assert "Pallet weight" in errors["pallet_weight_kg"]


def test_pallet_weight_values_from_registration_formats_decimals():
    values = pallet_weights.values_from_registration(
        EggPalletWeightRegistration(
            house_id="main",
            registration_date=date(2026, 5, 26),
            weekday="Dinsdag",
            packaging_weight_config_id=1,
            supplier_name="Eierhandel A",
            pallet_weight_kg=Decimal("700.000"),
            empty_packaging_weight_kg=Decimal("48.500"),
            egg_count_per_pallet=10800,
            egg_weight_grams=Decimal("60.3241"),
        )
    )

    assert values["registration_date"] == "2026-05-26"
    assert values["pallet_weight_kg"] == "700.000"
    assert values["empty_packaging_weight_kg"] == "48.500"
    assert values["egg_weight_grams"] == "60.3241"


def _packaging_config() -> EggPackagingWeightConfig:
    return EggPackagingWeightConfig(
        id=1,
        supplier_name="Eierhandel A",
        empty_packaging_weight_kg=Decimal("48.500"),
        egg_count_per_pallet=10800,
        start_date=date(2026, 5, 1),
    )
