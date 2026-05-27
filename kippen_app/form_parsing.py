"""Shared form parsing helpers for the Kippen app."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_date(
    raw_value: str,
    *,
    field_name: str,
    label: str,
    errors: dict[str, str],
    required: bool = True,
) -> Optional[date]:
    """Parse an ISO date field and record user-facing validation errors."""
    value = raw_value.strip()
    if value == "":
        if required:
            errors[field_name] = f"{label} is verplicht."
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        errors[field_name] = f"{label} is ongeldig."
        return None


def parse_decimal(
    raw_value: str,
    *,
    field_name: str,
    label: str,
    errors: dict[str, str],
    required: bool = True,
    allow_negative: bool = False,
) -> Optional[Decimal]:
    """Parse a decimal field, accepting both comma and dot decimal separators."""
    value = raw_value.strip().replace(",", ".")
    if value == "":
        if required:
            errors[field_name] = f"{label} is verplicht."
        return None

    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        errors[field_name] = f"{label} moet een getal zijn."
        return None

    if not decimal_value.is_finite():
        errors[field_name] = f"{label} moet een getal zijn."
        return None

    if decimal_value < 0 and not allow_negative:
        errors[field_name] = f"{label} mag niet negatief zijn."
        return None

    return decimal_value


def parse_int(
    raw_value: str,
    *,
    field_name: str,
    label: str,
    errors: dict[str, str],
    required: bool = True,
    minimum: Optional[int] = None,
) -> Optional[int]:
    """Parse an integer field and validate an optional minimum."""
    value = raw_value.strip()
    if value == "":
        if required:
            errors[field_name] = f"{label} is verplicht."
        return None

    try:
        int_value = int(value)
    except ValueError:
        errors[field_name] = f"{label} moet een heel getal zijn."
        return None

    if minimum is not None and int_value < minimum:
        errors[field_name] = f"{label} moet minimaal {minimum} zijn."
        return None

    return int_value


def format_decimal(value: Decimal) -> str:
    """Format a Decimal for form values without scientific notation."""
    return format(value, "f")
