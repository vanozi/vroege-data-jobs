"""Parse Tank Terminal transaction table HTML."""

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from typing import Optional

import lxml.html as lh


TRANSACTION_COLUMNS = [
    "vehicle",
    "driver",
    "transaction_type",
    "acquisition_mode",
    "transaction_status",
    "start_date_time",
    "transaction_number",
    "product",
    "quantity",
    "transaction_duration",
    "meter",
]

TANK_TERMINAL_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


@dataclass(frozen=True)
class ParsedTankTransaction:
    """Normalized Tank Terminal transaction row."""

    vehicle: Optional[str]
    driver: Optional[str]
    transaction_type: Optional[str]
    acquisition_mode: Optional[str]
    transaction_status: Optional[str]
    start_date_time: datetime
    transaction_number: str
    product: Optional[str]
    quantity_liters: float
    transaction_duration_seconds: Optional[int]
    meter_value: Optional[float]
    meter_type: Optional[str]


def parse_transactions_table(html: str) -> list[ParsedTankTransaction]:
    """Parse normalized Tank Terminal transaction rows from a table fragment."""
    normalized_html = unicodedata.normalize("NFKD", html)
    tree = lh.fragment_fromstring(normalized_html, create_parent=True)

    transactions = []
    for row in tree.xpath(".//tr"):
        cells = [_clean_text(cell.text_content()) for cell in row.xpath("./td")]
        data_cells = _extract_transaction_cells(cells)
        if data_cells is None:
            continue

        transactions.append(_parse_transaction_cells(data_cells))

    return transactions


def _extract_transaction_cells(cells: list[str]) -> Optional[list[str]]:
    if len(cells) < len(TRANSACTION_COLUMNS):
        return None

    candidate_cells = cells
    if candidate_cells and candidate_cells[0] == "":
        candidate_cells = candidate_cells[1:]
    if candidate_cells and candidate_cells[-1] == "":
        candidate_cells = candidate_cells[:-1]

    if len(candidate_cells) != len(TRANSACTION_COLUMNS):
        return None

    if candidate_cells == TRANSACTION_COLUMNS:
        return None

    transaction_number = candidate_cells[6]
    if not transaction_number or not re.fullmatch(r"\d+", transaction_number):
        return None

    return candidate_cells


def _parse_transaction_cells(cells: list[str]) -> ParsedTankTransaction:
    values = dict(zip(TRANSACTION_COLUMNS, cells))
    return ParsedTankTransaction(
        vehicle=_optional_text(values["vehicle"]),
        driver=_optional_text(values["driver"]),
        transaction_type=_optional_text(values["transaction_type"]),
        acquisition_mode=_optional_text(values["acquisition_mode"]),
        transaction_status=_optional_text(values["transaction_status"]),
        start_date_time=_parse_datetime(values["start_date_time"]),
        transaction_number=values["transaction_number"],
        product=_optional_text(values["product"]),
        quantity_liters=_parse_quantity_liters(values["quantity"]),
        transaction_duration_seconds=_parse_duration_seconds(
            values["transaction_duration"]
        ),
        meter_value=_parse_meter_value(values["meter"]),
        meter_type=_parse_meter_type(values["meter"]),
    )


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _optional_text(value: str) -> Optional[str]:
    cleaned_value = _clean_text(value)
    if cleaned_value == "":
        return None

    return cleaned_value


def _parse_datetime(value: str) -> datetime:
    return datetime.strptime(_clean_text(value), TANK_TERMINAL_DATETIME_FORMAT)


def _parse_quantity_liters(value: str) -> float:
    normalized_value = _clean_text(value).removesuffix(" L").strip()
    return float(normalized_value)


def _parse_duration_seconds(value: str) -> Optional[int]:
    normalized_value = _clean_text(value)
    if not normalized_value:
        return None

    parts = normalized_value.split(":")
    if len(parts) != 3:
        return None

    hours, minutes, seconds = [int(part) for part in parts]
    return hours * 3600 + minutes * 60 + seconds


def _parse_meter_value(value: str) -> Optional[float]:
    normalized_value = _clean_text(value)
    if not normalized_value:
        return None

    if normalized_value.endswith(" h"):
        return float(normalized_value.removesuffix(" h").strip())
    if normalized_value.endswith(" km"):
        return float(normalized_value.removesuffix(" km").strip())

    return None


def _parse_meter_type(value: str) -> Optional[str]:
    normalized_value = _clean_text(value)
    if normalized_value.endswith(" h"):
        return "h"
    if normalized_value.endswith(" km"):
        return "km"

    return None
