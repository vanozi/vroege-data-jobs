"""Calculation helpers for laying hens registrations."""

from decimal import Decimal, ROUND_HALF_UP


EGG_WEIGHT_GRAMS_PRECISION = Decimal("0.0001")


def calculate_egg_weight_grams(
    *,
    pallet_weight_kg: Decimal,
    empty_packaging_weight_kg: Decimal,
    egg_count_per_pallet: int,
) -> Decimal:
    """Calculate average egg weight in grams for one pallet."""
    if pallet_weight_kg < empty_packaging_weight_kg:
        raise ValueError("Pallet weight cannot be lower than empty packaging weight.")

    if egg_count_per_pallet <= 0:
        raise ValueError("Egg count per pallet must be greater than zero.")

    return (
        (pallet_weight_kg - empty_packaging_weight_kg)
        / Decimal(egg_count_per_pallet)
        * Decimal("1000")
    ).quantize(EGG_WEIGHT_GRAMS_PRECISION, rounding=ROUND_HALF_UP)
