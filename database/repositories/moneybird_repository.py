"""Repositories for Moneybird models."""

from typing import Union

from database.models.moneybird import MoneybirdAdministration
from database.models.moneybird import MoneybirdCollectionRun
from database.models.moneybird import MoneybirdContact
from database.models.moneybird import MoneybirdFinancialAccount
from database.models.moneybird import MoneybirdFinancialMutation
from database.models.moneybird import MoneybirdLedgerAccount
from database.models.moneybird import MoneybirdPurchaseInvoice
from database.models.moneybird import MoneybirdReportSnapshot
from database.models.moneybird import MoneybirdSalesInvoice
from database.repositories.base_repository import BaseRepository


class MoneybirdAdministrationsRepository(BaseRepository[MoneybirdAdministration]):
    """Repository for Moneybird administrations."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdAdministration, session_factory)

    def upsert_moneybird_administration(
        self,
        data: Union[dict[str, object], MoneybirdAdministration],
    ) -> MoneybirdAdministration:
        """Insert or update a Moneybird administration by Moneybird ID."""
        return self.upsert(_dump_model(data), unique_fields=["moneybird_id"])


class MoneybirdContactsRepository(BaseRepository[MoneybirdContact]):
    """Repository for Moneybird contacts."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdContact, session_factory)

    def upsert_moneybird_contact(
        self,
        data: Union[dict[str, object], MoneybirdContact],
    ) -> MoneybirdContact:
        """Insert or update a Moneybird contact by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdLedgerAccountsRepository(BaseRepository[MoneybirdLedgerAccount]):
    """Repository for Moneybird ledger accounts."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdLedgerAccount, session_factory)

    def upsert_moneybird_ledger_account(
        self,
        data: Union[dict[str, object], MoneybirdLedgerAccount],
    ) -> MoneybirdLedgerAccount:
        """Insert or update a Moneybird ledger account by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdSalesInvoicesRepository(BaseRepository[MoneybirdSalesInvoice]):
    """Repository for Moneybird sales invoices."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdSalesInvoice, session_factory)

    def upsert_moneybird_sales_invoice(
        self,
        data: Union[dict[str, object], MoneybirdSalesInvoice],
    ) -> MoneybirdSalesInvoice:
        """Insert or update a Moneybird sales invoice by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdPurchaseInvoicesRepository(BaseRepository[MoneybirdPurchaseInvoice]):
    """Repository for Moneybird purchase invoices."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdPurchaseInvoice, session_factory)

    def upsert_moneybird_purchase_invoice(
        self,
        data: Union[dict[str, object], MoneybirdPurchaseInvoice],
    ) -> MoneybirdPurchaseInvoice:
        """Insert or update a Moneybird purchase invoice by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdFinancialAccountsRepository(BaseRepository[MoneybirdFinancialAccount]):
    """Repository for Moneybird financial accounts."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdFinancialAccount, session_factory)

    def upsert_moneybird_financial_account(
        self,
        data: Union[dict[str, object], MoneybirdFinancialAccount],
    ) -> MoneybirdFinancialAccount:
        """Insert or update a Moneybird financial account by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdFinancialMutationsRepository(BaseRepository[MoneybirdFinancialMutation]):
    """Repository for Moneybird financial mutations."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdFinancialMutation, session_factory)

    def upsert_moneybird_financial_mutation(
        self,
        data: Union[dict[str, object], MoneybirdFinancialMutation],
    ) -> MoneybirdFinancialMutation:
        """Insert or update a Moneybird financial mutation by administration and ID."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "moneybird_id"],
        )


class MoneybirdReportSnapshotsRepository(BaseRepository[MoneybirdReportSnapshot]):
    """Repository for Moneybird report snapshots."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdReportSnapshot, session_factory)

    def upsert_moneybird_report_snapshot(
        self,
        data: Union[dict[str, object], MoneybirdReportSnapshot],
    ) -> MoneybirdReportSnapshot:
        """Insert or update a Moneybird report snapshot by report type and period."""
        return self.upsert(
            _dump_model(data),
            unique_fields=["administration_id", "report_type", "period"],
        )


class MoneybirdCollectionRunsRepository(BaseRepository[MoneybirdCollectionRun]):
    """Repository for Moneybird collection run audit records."""

    def __init__(self, session_factory):
        super().__init__(MoneybirdCollectionRun, session_factory)

    def create_moneybird_collection_run(
        self,
        data: Union[dict[str, object], MoneybirdCollectionRun],
    ) -> MoneybirdCollectionRun:
        """Create a Moneybird collection run audit row."""
        return self.create(_dump_model(data))


def _dump_model(data):
    if hasattr(data, "model_dump"):
        return data.model_dump()

    return data
