"""Collectors for Moneybird dashboard data."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Optional

from data_jobs.moneybird.api_client import MoneybirdClient
from data_jobs.moneybird.config import MoneybirdConfig
from data_jobs.moneybird import transforms
from data_jobs.moneybird.exceptions import MoneybirdConfigError


@dataclass(frozen=True)
class MoneybirdDashboardCollectionResult:
    """Dashboard-critical Moneybird records."""

    report_snapshots: list[dict[str, object]] = field(default_factory=list)
    sales_invoices: list[dict[str, object]] = field(default_factory=list)
    purchase_invoices: list[dict[str, object]] = field(default_factory=list)
    contacts: list[dict[str, object]] = field(default_factory=list)
    ledger_accounts: list[dict[str, object]] = field(default_factory=list)
    financial_accounts: list[dict[str, object]] = field(default_factory=list)
    financial_mutations: list[dict[str, object]] = field(default_factory=list)

    def summary_counts(self) -> dict[str, int]:
        """Return counts for CLI output and logging."""
        return {
            "report_snapshots": len(self.report_snapshots),
            "sales_invoices": len(self.sales_invoices),
            "purchase_invoices": len(self.purchase_invoices),
            "contacts": len(self.contacts),
            "ledger_accounts": len(self.ledger_accounts),
            "financial_accounts": len(self.financial_accounts),
            "financial_mutations": len(self.financial_mutations),
        }


def collect_dashboard_records(
    client: MoneybirdClient,
    config: MoneybirdConfig,
    *,
    administration_id: Optional[str] = None,
    period: Optional[str] = None,
    sync_reports: bool = True,
    sync_sales_invoices: bool = True,
    sync_purchase_invoices: bool = True,
    sync_contacts: bool = True,
    sync_ledger_accounts: bool = True,
    sync_financial_accounts: bool = True,
    sync_financial_mutations: bool = True,
    logger: Optional[logging.Logger] = None,
) -> MoneybirdDashboardCollectionResult:
    """Collect Moneybird rows needed for the bookkeeping dashboard."""
    _log_progress(logger, "Resolving Moneybird administration.")
    resolved_administration_id = _resolve_administration_id(
        client,
        config,
        administration_id,
    )
    resolved_period = period or config.default_period
    synced_at = datetime.now(UTC)
    _log_progress(
        logger,
        "Starting Moneybird collection for administration=%s period=%s.",
        resolved_administration_id,
        resolved_period,
    )

    report_snapshots = []
    if sync_reports:
        _log_progress(logger, "Collecting report snapshots.")
        report_snapshots = collect_report_snapshots(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
        )
        _log_progress(logger, "Collected %s report snapshots.", len(report_snapshots))
    else:
        _log_progress(logger, "Skipping report snapshots.")

    sales_invoices = []
    if sync_sales_invoices:
        _log_progress(logger, "Collecting sales invoices.")
        sales_invoices = collect_sales_invoices(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(logger, "Collected %s sales invoices.", len(sales_invoices))
    else:
        _log_progress(logger, "Skipping sales invoices.")

    purchase_invoices = []
    if sync_purchase_invoices:
        _log_progress(logger, "Collecting purchase invoices.")
        purchase_invoices = collect_purchase_invoices(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(
            logger,
            "Collected %s purchase invoices.",
            len(purchase_invoices),
        )
    else:
        _log_progress(logger, "Skipping purchase invoices.")

    contacts = []
    if sync_contacts:
        _log_progress(logger, "Collecting contacts.")
        contacts = collect_contacts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(logger, "Collected %s contacts.", len(contacts))
    else:
        _log_progress(logger, "Skipping contacts.")

    ledger_accounts = []
    if sync_ledger_accounts:
        _log_progress(logger, "Collecting ledger accounts.")
        ledger_accounts = collect_ledger_accounts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(logger, "Collected %s ledger accounts.", len(ledger_accounts))
    else:
        _log_progress(logger, "Skipping ledger accounts.")

    financial_accounts = []
    if sync_financial_accounts:
        _log_progress(logger, "Collecting financial accounts.")
        financial_accounts = collect_financial_accounts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(
            logger,
            "Collected %s financial accounts.",
            len(financial_accounts),
        )
    else:
        _log_progress(logger, "Skipping financial accounts.")

    financial_mutations = []
    if sync_financial_mutations:
        _log_progress(logger, "Collecting financial mutations.")
        financial_mutations = collect_financial_mutations(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
            logger=logger,
        )
        _log_progress(
            logger,
            "Collected %s financial mutations.",
            len(financial_mutations),
        )
    else:
        _log_progress(logger, "Skipping financial mutations.")

    _log_progress(logger, "Moneybird collection completed.")

    return MoneybirdDashboardCollectionResult(
        report_snapshots=report_snapshots,
        sales_invoices=sales_invoices,
        purchase_invoices=purchase_invoices,
        contacts=contacts,
        ledger_accounts=ledger_accounts,
        financial_accounts=financial_accounts,
        financial_mutations=financial_mutations,
    )


def collect_report_snapshots(
    client: MoneybirdClient,
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
) -> list[dict[str, object]]:
    """Collect profit/loss and balance sheet report snapshots."""
    profit_loss = client.get_json(
        f"/{administration_id}/reports/profit_loss.json",
        params={"period": period},
    )
    balance_sheet = client.get_json(
        f"/{administration_id}/reports/balance_sheet.json",
        params={"period": period},
    )

    if not isinstance(profit_loss, dict):
        raise ValueError("Moneybird profit/loss report response was not an object.")
    if not isinstance(balance_sheet, dict):
        raise ValueError("Moneybird balance sheet report response was not an object.")

    return [
        transforms.transform_profit_loss_report(
            profit_loss,
            administration_id=administration_id,
            period=period,
            synced_at=synced_at,
        ),
        transforms.transform_balance_sheet_report(
            balance_sheet,
            administration_id=administration_id,
            period=period,
            synced_at=synced_at,
        ),
    ]


def collect_sales_invoices(
    client: MoneybirdClient,
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird sales invoices."""
    rows = client.get_paginated(
        f"/{administration_id}/sales_invoices.json",
        params={"filter": f"period:{period},state:all"},
        logger=logger,
    )
    return [
        transforms.transform_sales_invoice(
            row,
            administration_id=administration_id,
            synced_at=synced_at,
        )
        for row in rows
    ]


def collect_purchase_invoices(
    client: MoneybirdClient,
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird purchase invoices."""
    rows = client.get_paginated(
        f"/{administration_id}/documents/purchase_invoices.json",
        params={"filter": f"period:{period},state:all"},
        logger=logger,
    )
    return [
        transforms.transform_purchase_invoice(
            row,
            administration_id=administration_id,
            synced_at=synced_at,
        )
        for row in rows
    ]


def collect_contacts(
    client: MoneybirdClient,
    *,
    administration_id: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird contacts."""
    rows = client.get_paginated(f"/{administration_id}/contacts.json", logger=logger)
    return [
        transforms.transform_contact(
            row,
            administration_id=administration_id,
            synced_at=synced_at,
        )
        for row in rows
    ]


def collect_ledger_accounts(
    client: MoneybirdClient,
    *,
    administration_id: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird ledger accounts."""
    rows = client.get_paginated(
        f"/{administration_id}/ledger_accounts.json",
        logger=logger,
    )
    return [
        transforms.transform_ledger_account(
            row,
            administration_id=administration_id,
            synced_at=synced_at,
        )
        for row in rows
    ]


def collect_financial_accounts(
    client: MoneybirdClient,
    *,
    administration_id: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird financial accounts."""
    rows = client.get_paginated(
        f"/{administration_id}/financial_accounts.json",
        logger=logger,
    )
    return [
        transforms.transform_financial_account(
            row,
            administration_id=administration_id,
            synced_at=synced_at,
        )
        for row in rows
    ]


def collect_financial_mutations(
    client: MoneybirdClient,
    *,
    administration_id: str,
    period: str,
    synced_at: datetime,
    logger: Optional[logging.Logger] = None,
) -> list[dict[str, object]]:
    """Collect Moneybird financial mutations through synchronization."""
    synchronization_path = (
        f"/{administration_id}/financial_mutations/synchronization.json"
    )
    _log_progress(logger, "Fetching financial mutation synchronization index.")
    synchronization_rows = client.get_paginated(
        synchronization_path,
        params={"filter": f"period:{period},state:all"},
        logger=logger,
    )
    mutation_ids = [
        str(row["id"])
        for row in synchronization_rows
        if isinstance(row.get("id"), str | int)
    ]
    total_batches = (len(mutation_ids) + 99) // 100
    _log_progress(
        logger,
        "Financial mutation synchronization index returned %s ids in %s batches.",
        len(mutation_ids),
        total_batches,
    )
    mutations: list[dict[str, object]] = []

    for batch_number, batch in enumerate(_chunks(mutation_ids, 100), start=1):
        _log_progress(
            logger,
            "Fetching financial mutation batch %s/%s.",
            batch_number,
            total_batches,
        )
        response = client.post_json(synchronization_path, json={"ids": batch})
        if not isinstance(response, list):
            raise ValueError(
                "Moneybird financial mutations synchronization response was not a list."
            )

        for row in response:
            if not isinstance(row, dict):
                raise ValueError(
                    "Moneybird financial mutations response contained a non-object item."
                )
            mutations.append(
                transforms.transform_financial_mutation(
                    row,
                    administration_id=administration_id,
                    synced_at=synced_at,
                )
            )
        _log_progress(
            logger,
            "Processed financial mutation batch %s/%s; total mutations=%s.",
            batch_number,
            total_batches,
            len(mutations),
        )

    return mutations


def _resolve_administration_id(
    client: MoneybirdClient,
    config: MoneybirdConfig,
    administration_id: Optional[str],
) -> str:
    if administration_id:
        return administration_id
    if config.administration_id:
        return config.administration_id

    administrations = client.list_administrations()
    for administration in administrations:
        if administration.get("name") == config.administration_name:
            return str(administration["id"])

    raise MoneybirdConfigError(
        "Moneybird administration ID is required or an accessible administration "
        f"named {config.administration_name!r} must exist."
    )


def _chunks(values: list[str], size: int) -> Iterator[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _log_progress(
    logger: Optional[logging.Logger],
    message: str,
    *args: object,
) -> None:
    if logger is None:
        return

    logger.info(message, *args)
