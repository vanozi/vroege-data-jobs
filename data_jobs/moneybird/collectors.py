"""Collectors for Moneybird dashboard data."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
) -> MoneybirdDashboardCollectionResult:
    """Collect Moneybird rows needed for the bookkeeping dashboard."""
    resolved_administration_id = _resolve_administration_id(
        client,
        config,
        administration_id,
    )
    resolved_period = period or config.default_period
    synced_at = datetime.now(UTC)

    report_snapshots = []
    if sync_reports:
        report_snapshots = collect_report_snapshots(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
        )

    sales_invoices = []
    if sync_sales_invoices:
        sales_invoices = collect_sales_invoices(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
        )

    purchase_invoices = []
    if sync_purchase_invoices:
        purchase_invoices = collect_purchase_invoices(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
        )

    contacts = []
    if sync_contacts:
        contacts = collect_contacts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
        )

    ledger_accounts = []
    if sync_ledger_accounts:
        ledger_accounts = collect_ledger_accounts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
        )

    financial_accounts = []
    if sync_financial_accounts:
        financial_accounts = collect_financial_accounts(
            client,
            administration_id=resolved_administration_id,
            synced_at=synced_at,
        )

    financial_mutations = []
    if sync_financial_mutations:
        financial_mutations = collect_financial_mutations(
            client,
            administration_id=resolved_administration_id,
            period=resolved_period,
            synced_at=synced_at,
        )

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
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird sales invoices."""
    rows = client.get_paginated(
        f"/{administration_id}/sales_invoices.json",
        params={"filter": f"period:{period},state:all"},
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
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird purchase invoices."""
    rows = client.get_paginated(
        f"/{administration_id}/documents/purchase_invoices.json",
        params={"filter": f"period:{period},state:all"},
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
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird contacts."""
    rows = client.get_paginated(f"/{administration_id}/contacts.json")
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
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird ledger accounts."""
    rows = client.get_paginated(f"/{administration_id}/ledger_accounts.json")
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
) -> list[dict[str, object]]:
    """Collect and normalize Moneybird financial accounts."""
    rows = client.get_paginated(f"/{administration_id}/financial_accounts.json")
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
) -> list[dict[str, object]]:
    """Collect Moneybird financial mutations through synchronization."""
    synchronization_path = (
        f"/{administration_id}/financial_mutations/synchronization.json"
    )
    synchronization_rows = client.get_paginated(
        synchronization_path,
        params={"filter": f"period:{period},state:all"},
    )
    mutation_ids = [
        str(row["id"])
        for row in synchronization_rows
        if isinstance(row.get("id"), str | int)
    ]
    mutations: list[dict[str, object]] = []

    for batch in _chunks(mutation_ids, 100):
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
