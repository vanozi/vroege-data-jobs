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
HEADER_LABELS = {
    "vehicle": "vehicle",
    "driver": "driver",
    "transaction type": "transaction_type",
    "acquisition mode": "acquisition_mode",
    "transaction status": "transaction_status",
    "start date-time": "start_date_time",
    "transaction number": "transaction_number",
    "product": "product",
    "quantity": "quantity",
    "transaction duration": "transaction_duration",
    "meter": "meter",
}


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
    active_header: Optional[list[str]] = None
    for row in tree.xpath(".//tr"):
        cells = [_clean_text(cell.text_content()) for cell in row.xpath("./td")]
        header = _extract_header(cells)
        if header is not None:
            active_header = header
            continue

        row_values = _extract_transaction_values(cells, active_header)
        if row_values is None:
            continue

        transactions.append(_parse_transaction_values(row_values))

    return transactions


def _extract_header(cells: list[str]) -> Optional[list[str]]:
    candidate_cells = _trim_empty_edges(cells)
    header = [_normalize_header_label(cell) for cell in candidate_cells]
    matched_header = [HEADER_LABELS[cell] for cell in header if cell in HEADER_LABELS]
    if len(matched_header) < 3:
        return None

    if not {"driver", "vehicle", "product"}.issubset(set(matched_header)):
        return None

    return [HEADER_LABELS[cell] for cell in header if cell in HEADER_LABELS]


def _extract_transaction_values(
    cells: list[str],
    active_header: Optional[list[str]],
) -> Optional[dict[str, str]]:
    candidate_cells = _trim_empty_edges(cells)
    if not candidate_cells:
        return None

    if active_header is not None and len(candidate_cells) >= len(active_header):
        row_values = dict(zip(active_header, candidate_cells[: len(active_header)]))
        if _is_transaction_row(row_values):
            return row_values

    return _extract_transaction_values_by_pattern(candidate_cells)


def _extract_transaction_values_by_pattern(
    cells: list[str],
) -> Optional[dict[str, str]]:
    transaction_number = next(
        (cell for cell in cells if re.fullmatch(r"\d{6,}", cell)),
        None,
    )
    start_date_time = next((cell for cell in cells if _looks_like_datetime(cell)), None)
    quantity = next((cell for cell in cells if _clean_text(cell).endswith(" L")), None)
    if transaction_number is None or start_date_time is None or quantity is None:
        return None

    transaction_duration = next(
        (cell for cell in cells if re.fullmatch(r"\d{2}:\d{2}:\d{2}", cell)),
        "",
    )
    meter = next(
        (
            cell
            for cell in cells
            if _clean_text(cell).endswith((" h", " km"))
            and not _clean_text(cell).endswith(" L")
        ),
        "",
    )
    product = next((cell for cell in cells if cell.lower() == "diesel"), "")
    product_index = cells.index(product) if product else -1
    leading_cells = [cell for cell in cells[:product_index] if cell]

    return {
        "driver": leading_cells[0] if len(leading_cells) >= 1 else "",
        "vehicle": leading_cells[1] if len(leading_cells) >= 2 else "",
        "transaction_type": "",
        "acquisition_mode": "",
        "transaction_status": "",
        "start_date_time": start_date_time,
        "transaction_number": transaction_number,
        "product": product,
        "quantity": quantity,
        "transaction_duration": transaction_duration,
        "meter": meter,
    }


def _parse_transaction_values(values: dict[str, str]) -> ParsedTankTransaction:
    return ParsedTankTransaction(
        vehicle=_optional_text(values.get("vehicle", "")),
        driver=_optional_text(values.get("driver", "")),
        transaction_type=_optional_text(values.get("transaction_type", "")),
        acquisition_mode=_optional_text(values.get("acquisition_mode", "")),
        transaction_status=_optional_text(values.get("transaction_status", "")),
        start_date_time=_parse_datetime(values["start_date_time"]),
        transaction_number=values["transaction_number"],
        product=_optional_text(values.get("product", "")),
        quantity_liters=_parse_quantity_liters(values["quantity"]),
        transaction_duration_seconds=_parse_duration_seconds(
            values.get("transaction_duration", "")
        ),
        meter_value=_parse_meter_value(values.get("meter", "")),
        meter_type=_parse_meter_type(values.get("meter", "")),
    )


def _trim_empty_edges(cells: list[str]) -> list[str]:
    candidate_cells = list(cells)
    while candidate_cells and candidate_cells[0] == "":
        candidate_cells = candidate_cells[1:]
    while candidate_cells and candidate_cells[-1] == "":
        candidate_cells = candidate_cells[:-1]

    return candidate_cells


def _normalize_header_label(value: str) -> str:
    return _clean_text(value).lower()


def _is_transaction_row(values: dict[str, str]) -> bool:
    transaction_number = values.get("transaction_number", "")
    if not re.fullmatch(r"\d{6,}", transaction_number):
        return False

    return _looks_like_datetime(values.get("start_date_time", "")) and values.get(
        "quantity", ""
    ).endswith(" L")


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _optional_text(value: str) -> Optional[str]:
    cleaned_value = _clean_text(value)
    if cleaned_value == "":
        return None

    return cleaned_value


def _parse_datetime(value: str) -> datetime:
    return datetime.strptime(_clean_text(value), TANK_TERMINAL_DATETIME_FORMAT)


def _looks_like_datetime(value: str) -> bool:
    try:
        _parse_datetime(value)
    except ValueError:
        return False

    return True


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
