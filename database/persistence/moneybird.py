"""Persistence helpers for Moneybird data."""

import logging
from typing import Optional

from database.repositories.moneybird_repository import (
    MoneybirdAdministrationsRepository,
    MoneybirdContactsRepository,
    MoneybirdFinancialAccountsRepository,
    MoneybirdFinancialMutationsRepository,
    MoneybirdLedgerAccountsRepository,
    MoneybirdPurchaseInvoicesRepository,
    MoneybirdReportSnapshotsRepository,
    MoneybirdSalesInvoicesRepository,
)


def save_moneybird_administrations(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdAdministrationsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird administrations and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_administration",
        "Moneybird administrations",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_contacts(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdContactsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird contacts and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_contact",
        "Moneybird contacts",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_ledger_accounts(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdLedgerAccountsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird ledger accounts and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_ledger_account",
        "Moneybird ledger accounts",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_sales_invoices(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdSalesInvoicesRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird sales invoices and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_sales_invoice",
        "Moneybird sales invoices",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_purchase_invoices(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdPurchaseInvoicesRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird purchase invoices and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_purchase_invoice",
        "Moneybird purchase invoices",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_financial_accounts(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdFinancialAccountsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird financial accounts and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_financial_account",
        "Moneybird financial accounts",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_financial_mutations(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdFinancialMutationsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird financial mutations and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_financial_mutation",
        "Moneybird financial mutations",
        dry_run=dry_run,
        logger=logger,
    )


def save_moneybird_report_snapshots(
    rows: list[dict[str, object]],
    repository: Optional[MoneybirdReportSnapshotsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert Moneybird report snapshots and return the number processed."""
    return _save_rows(
        rows,
        repository,
        "upsert_moneybird_report_snapshot",
        "Moneybird report snapshots",
        dry_run=dry_run,
        logger=logger,
    )


def _save_rows(
    rows: list[dict[str, object]],
    repository: object,
    upsert_method_name: str,
    label: str,
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    if dry_run:
        _log_count(logger, "Dry run: would save %d %s.", len(rows), label)
        return len(rows)

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    upsert = getattr(repository, upsert_method_name)
    saved_count = 0
    for row in rows:
        upsert(row)
        saved_count += 1

    _log_count(logger, "Saved %d %s.", saved_count, label)
    return saved_count


def _log_count(
    logger: Optional[logging.Logger],
    message: str,
    count: int,
    label: str,
) -> None:
    if logger is None:
        return

    logger.info(message, count, label)
