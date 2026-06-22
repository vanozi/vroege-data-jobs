"""Transform Moneybird API responses into database rows."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


def transform_profit_loss_report(
    report: dict[str, object],
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird profit/loss report snapshot."""
    return {
        "administration_id": administration_id,
        "report_type": "profit_loss",
        "period": period,
        "total_revenue": _parse_decimal(report.get("total_revenue")),
        "total_expenses": _parse_decimal(report.get("total_expenses")),
        "gross_profit": _parse_decimal(report.get("gross_profit")),
        "operating_profit": _parse_decimal(report.get("operating_profit")),
        "net_profit": _parse_decimal(report.get("net_profit")),
        "raw_json": report,
        "synced_at": synced_at,
    }


def transform_balance_sheet_report(
    report: dict[str, object],
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird balance sheet report snapshot."""
    return {
        "administration_id": administration_id,
        "report_type": "balance_sheet",
        "period": period,
        "raw_json": report,
        "synced_at": synced_at,
    }


def transform_sales_invoice(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird sales invoice row."""
    contact = _dict_value(row.get("contact"))
    return {
        "administration_id": administration_id,
        "moneybird_id": _required_text(row.get("id"), "sales invoice id"),
        "invoice_id": _optional_text(row.get("invoice_id")),
        "contact_id": _optional_text(row.get("contact_id") or contact.get("id")),
        "contact_name": _contact_name(row, contact),
        "state": _optional_text(row.get("state")),
        "invoice_date": _parse_date(row.get("invoice_date")),
        "due_date": _parse_date(row.get("due_date")),
        "paid_at": _parse_date(row.get("paid_at")),
        "sent_at": _parse_datetime(row.get("sent_at")),
        "currency": _optional_text(row.get("currency")),
        "total_price_excl_tax": _parse_decimal(row.get("total_price_excl_tax")),
        "total_price_incl_tax": _parse_decimal(row.get("total_price_incl_tax")),
        "total_paid": _parse_decimal(row.get("total_paid")),
        "total_unpaid": _parse_decimal(row.get("total_unpaid")),
        "marked_dubious_on": _parse_date(row.get("marked_dubious_on")),
        "marked_uncollectible_on": _parse_date(row.get("marked_uncollectible_on")),
        "reminder_count": _parse_int(row.get("reminder_count")),
        "next_reminder": _parse_date(row.get("next_reminder")),
        "moneybird_version": _parse_int(row.get("version")),
        "moneybird_updated_at": _parse_datetime(row.get("updated_at")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def transform_purchase_invoice(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird purchase invoice row."""
    contact = _dict_value(row.get("contact"))
    return {
        "administration_id": administration_id,
        "moneybird_id": _required_text(row.get("id"), "purchase invoice id"),
        "contact_id": _optional_text(row.get("contact_id") or contact.get("id")),
        "contact_name": _contact_name(row, contact),
        "reference": _optional_text(row.get("reference")),
        "entry_number": _parse_int(row.get("entry_number")),
        "state": _optional_text(row.get("state")),
        "date": _parse_date(row.get("date")),
        "due_date": _parse_date(row.get("due_date")),
        "paid_at": _parse_date(row.get("paid_at")),
        "currency": _optional_text(row.get("currency")),
        "total_price_excl_tax": _parse_decimal(row.get("total_price_excl_tax")),
        "total_price_incl_tax": _parse_decimal(row.get("total_price_incl_tax")),
        "total_price_excl_tax_base": _parse_decimal(
            row.get("total_price_excl_tax_base")
        ),
        "total_price_incl_tax_base": _parse_decimal(
            row.get("total_price_incl_tax_base")
        ),
        "moneybird_version": _parse_int(row.get("version")),
        "moneybird_updated_at": _parse_datetime(row.get("updated_at")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def transform_contact(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird contact row."""
    return {
        "administration_id": administration_id,
        "moneybird_id": _required_text(row.get("id"), "contact id"),
        "company_name": _optional_text(row.get("company_name")),
        "firstname": _optional_text(row.get("firstname")),
        "lastname": _optional_text(row.get("lastname")),
        "customer_id": _optional_text(row.get("customer_id")),
        "supplier_id": _optional_text(row.get("supplier_id")),
        "email": _optional_text(row.get("email")),
        "city": _optional_text(row.get("city")),
        "country": _optional_text(row.get("country")),
        "archived": _parse_bool(row.get("archived")),
        "moneybird_version": _parse_int(row.get("version")),
        "moneybird_updated_at": _parse_datetime(row.get("updated_at")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def transform_ledger_account(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird ledger account row."""
    return {
        "administration_id": administration_id,
        "moneybird_id": _required_text(row.get("id"), "ledger account id"),
        "name": _required_text(row.get("name"), "ledger account name"),
        "account_type": _optional_text(row.get("account_type")),
        "account_id": _optional_text(row.get("account_id")),
        "moneybird_version": _parse_int(row.get("version")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def transform_financial_account(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird financial account row."""
    moneybird_id = _required_text(row.get("id"), "financial account id")
    return {
        "administration_id": administration_id,
        "moneybird_id": moneybird_id,
        "type": _optional_text(row.get("type")),
        "name": _required_text(
            row.get("name") or row.get("identifier") or moneybird_id,
            "financial account name",
        ),
        "identifier": _optional_text(row.get("identifier")),
        "currency": _optional_text(row.get("currency")),
        "provider": _optional_text(row.get("provider")),
        "active": _parse_bool(row.get("active")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def transform_financial_mutation(
    row: dict[str, object],
    *,
    administration_id: str,
    synced_at: datetime,
) -> dict[str, object]:
    """Normalize a Moneybird financial mutation row."""
    return {
        "administration_id": administration_id,
        "moneybird_id": _required_text(row.get("id"), "financial mutation id"),
        "financial_account_id": _optional_text(row.get("financial_account_id")),
        "amount": _parse_decimal(row.get("amount")),
        "amount_open": _parse_decimal(row.get("amount_open")),
        "date": _parse_date(row.get("date")),
        "message": _optional_text(row.get("message")),
        "code": _optional_text(row.get("code")),
        "contra_account_name": _optional_text(row.get("contra_account_name")),
        "contra_account_number": _optional_text(row.get("contra_account_number")),
        "state": _optional_text(row.get("state")),
        "settlement_state": _optional_text(row.get("settlement_state")),
        "moneybird_version": _parse_int(row.get("version")),
        "moneybird_updated_at": _parse_datetime(row.get("updated_at")),
        "raw_json": row,
        "synced_at": synced_at,
    }


def _parse_decimal(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Invalid Moneybird decimal value: {value}") from error


def _parse_date(value: object) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    value_text = str(value).strip()
    if not value_text:
        return None

    return datetime.fromisoformat(value_text[:10]).date()


def _parse_datetime(value: object) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value

    value_text = str(value).strip()
    if not value_text:
        return None

    return datetime.fromisoformat(value_text.replace("Z", "+00:00"))


def _parse_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None

    return int(value)


def _parse_bool(value: object) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value

    value_text = str(value).strip().lower()
    if value_text in {"true", "1", "yes"}:
        return True
    if value_text in {"false", "0", "no"}:
        return False

    raise ValueError(f"Invalid Moneybird boolean value: {value}")


def _required_text(value: object, label: str) -> str:
    text = _optional_text(value)
    if text:
        return text

    raise ValueError(f"Missing Moneybird {label}.")


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return text


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value

    return {}


def _contact_name(
    row: dict[str, object],
    contact: dict[str, object],
) -> Optional[str]:
    for value in (
        row.get("contact_name"),
        contact.get("company_name"),
        contact.get("name"),
    ):
        text = _optional_text(value)
        if text:
            return text

    first_name = _optional_text(contact.get("firstname"))
    last_name = _optional_text(contact.get("lastname"))
    full_name = " ".join(part for part in [first_name, last_name] if part)
    return full_name or None
