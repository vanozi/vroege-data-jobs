"""Parse Tank Terminal CSV exports."""

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Optional

from database.models.tank_transaction import TankTransaction


TANK_TERMINAL_DATE_FORMAT = "%d/%m/%Y"
TANK_TERMINAL_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


class TankTerminalCsvParseError(ValueError):
    """Raised when a Tank Terminal CSV row cannot be parsed."""


def parse_tank_transactions_csv_file(path: Path) -> list[TankTransaction]:
    """Parse Tank Terminal transactions from a CSV export file."""
    csv_text = path.read_text(encoding="utf-8-sig")
    return parse_tank_transactions_csv_text(csv_text)


def parse_tank_transactions_csv_text(csv_text: str) -> list[TankTransaction]:
    """Parse Tank Terminal transactions from CSV export text."""
    reader = csv.DictReader(StringIO(csv_text), delimiter=";")
    transactions = []

    for row_number, row in enumerate(reader, start=2):
        if _is_empty_row(row):
            continue

        transactions.append(_parse_csv_row(row, row_number))

    return transactions


def _parse_csv_row(row: dict[str, Optional[str]], row_number: int) -> TankTransaction:
    try:
        transaction = TankTransaction(
            transaction_number=_required_text(row, "Transaction number"),
            start_date_time=_required_datetime(row, "Start date-time"),
            transaction_date=_optional_date(row, "Transaction date"),
            transaction_hour=_optional_text(row, "Transaction hour"),
            vehicle=_optional_text(row, "Vehicle"),
            vehicle_number=_optional_text(row, "Vehicle - Number"),
            driver=_optional_text(row, "Driver"),
            driver_number=_optional_text(row, "Driver - Number"),
            product=_optional_text(row, "Product"),
            quantity_liters=_required_float(row, "Quantity"),
            quantity_units=_optional_text(row, "Quantity - Units"),
            dispenser=_optional_text(row, "Dispenser"),
            tank=_optional_text(row, "Tank"),
            odometer=_optional_float(row, "Odometer"),
            hours_counter=_optional_float(row, "Hours counter"),
            acquisition_mode=_optional_text(row, "Acquisition mode"),
            transaction_status=_optional_text(row, "Transaction status"),
            transaction_type=_optional_text(row, "Transaction type"),
            transaction_result=_optional_text(row, "Transaction result"),
            vehicle_identifier=_optional_text(row, "Vehicle identifier"),
            driver_identifier=_optional_text(row, "Driver identifier"),
        )
    except (KeyError, ValueError) as exc:
        raise TankTerminalCsvParseError(
            f"Could not parse Tank Terminal CSV row {row_number}: {exc}"
        ) from exc

    _set_legacy_meter_fields(transaction)
    return transaction


def _is_empty_row(row: dict[str, Optional[str]]) -> bool:
    return all(_clean_text(value) is None for value in row.values())


def _required_text(row: dict[str, Optional[str]], column_name: str) -> str:
    value = _optional_text(row, column_name)
    if value is None:
        raise ValueError(f"missing required column value: {column_name}")

    return value


def _optional_text(
    row: dict[str, Optional[str]],
    column_name: str,
) -> Optional[str]:
    if column_name not in row:
        raise KeyError(f"missing required column: {column_name}")

    return _clean_text(row[column_name])


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    cleaned_value = " ".join(value.replace("\xa0", " ").split())
    if cleaned_value == "":
        return None

    return cleaned_value


def _required_datetime(
    row: dict[str, Optional[str]],
    column_name: str,
) -> datetime:
    value = _required_text(row, column_name)
    return datetime.strptime(value, TANK_TERMINAL_DATETIME_FORMAT)


def _optional_date(
    row: dict[str, Optional[str]],
    column_name: str,
) -> Optional[date]:
    value = _optional_text(row, column_name)
    if value is None:
        return None

    return datetime.strptime(value, TANK_TERMINAL_DATE_FORMAT).date()


def _required_float(row: dict[str, Optional[str]], column_name: str) -> float:
    value = _optional_float(row, column_name)
    if value is None:
        raise ValueError(f"missing required column value: {column_name}")

    return value


def _optional_float(
    row: dict[str, Optional[str]],
    column_name: str,
) -> Optional[float]:
    value = _optional_text(row, column_name)
    if value is None:
        return None

    return _parse_european_float(value)


def _parse_european_float(value: str) -> float:
    normalized_value = value.replace(" ", "")
    if "," in normalized_value and "." in normalized_value:
        normalized_value = normalized_value.replace(".", "")

    normalized_value = normalized_value.replace(",", ".")
    return float(normalized_value)


def _set_legacy_meter_fields(transaction: TankTransaction) -> None:
    if transaction.hours_counter is not None:
        transaction.meter_value = transaction.hours_counter
        transaction.meter_type = "h"
        return

    if transaction.odometer is not None:
        transaction.meter_value = transaction.odometer
        transaction.meter_type = "km"
