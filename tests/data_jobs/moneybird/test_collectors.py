from data_jobs.moneybird import collectors
from data_jobs.moneybird.config import MoneybirdConfig


class FakeMoneybirdClient:
    def __init__(self):
        self.json_requests = []
        self.paginated_requests = []
        self.post_requests = []

    def get_json(self, path, params=None):
        self.json_requests.append((path, params))
        if path.endswith("/profit_loss.json"):
            return {"total_revenue": "1000.00", "net_profit": "100.00"}
        if path.endswith("/balance_sheet.json"):
            return {"assets": []}
        raise AssertionError(f"Unexpected path: {path}")

    def get_paginated(self, path, params=None):
        self.paginated_requests.append((path, params))
        if path.endswith("/sales_invoices.json"):
            return [
                {
                    "id": "sales-1",
                    "state": "open",
                    "invoice_date": "2026-06-01",
                }
            ]
        if path.endswith("/documents/purchase_invoices.json"):
            return [
                {
                    "id": "purchase-1",
                    "date": "2026-06-02",
                    "total_price_incl_tax": "121.00",
                }
            ]
        if path.endswith("/contacts.json"):
            return [{"id": "contact-1", "company_name": "Klant BV"}]
        if path.endswith("/ledger_accounts.json"):
            return [{"id": "ledger-1", "name": "Omzet"}]
        if path.endswith("/financial_accounts.json"):
            return [{"id": "account-1", "name": "Bank", "active": True}]
        if path.endswith("/financial_mutations/synchronization.json"):
            return [{"id": "mutation-1", "version": 2}]
        raise AssertionError(f"Unexpected path: {path}")

    def post_json(self, path, json=None):
        self.post_requests.append((path, json))
        if path.endswith("/financial_mutations/synchronization.json"):
            return [
                {
                    "id": "mutation-1",
                    "amount": "25.00",
                    "financial_account_id": "account-1",
                    "date": "2026-06-20",
                }
            ]
        raise AssertionError(f"Unexpected path: {path}")

    def list_administrations(self):
        return [{"id": "admin-1", "name": "Gebroeders vroege cv"}]


def build_config(**overrides):
    values = {
        "access_token": "token",
        "administration_name": "Gebroeders vroege cv",
        "default_period": "this_year",
    }
    values.update(overrides)
    return MoneybirdConfig(**values)


def test_collect_dashboard_records_collects_reports_and_invoices():
    client = FakeMoneybirdClient()

    result = collectors.collect_dashboard_records(
        client,
        build_config(administration_id="admin-1"),
    )

    assert result.summary_counts() == {
        "report_snapshots": 2,
        "sales_invoices": 1,
        "purchase_invoices": 1,
        "contacts": 1,
        "ledger_accounts": 1,
        "financial_accounts": 1,
        "financial_mutations": 1,
    }
    assert client.json_requests == [
        ("/admin-1/reports/profit_loss.json", {"period": "this_year"}),
        ("/admin-1/reports/balance_sheet.json", {"period": "this_year"}),
    ]
    assert client.paginated_requests == [
        (
            "/admin-1/sales_invoices.json",
            {"filter": "period:this_year,state:all"},
        ),
        (
            "/admin-1/documents/purchase_invoices.json",
            {"filter": "period:this_year,state:all"},
        ),
        ("/admin-1/contacts.json", None),
        ("/admin-1/ledger_accounts.json", None),
        ("/admin-1/financial_accounts.json", None),
        (
            "/admin-1/financial_mutations/synchronization.json",
            {"filter": "period:this_year,state:all"},
        ),
    ]
    assert client.post_requests == [
        (
            "/admin-1/financial_mutations/synchronization.json",
            {"ids": ["mutation-1"]},
        ),
    ]


def test_collect_dashboard_records_resolves_administration_by_name():
    client = FakeMoneybirdClient()

    result = collectors.collect_dashboard_records(
        client,
        build_config(administration_id=None),
        sync_reports=False,
        sync_sales_invoices=True,
        sync_purchase_invoices=False,
        sync_contacts=False,
        sync_ledger_accounts=False,
        sync_financial_accounts=False,
        sync_financial_mutations=False,
    )

    assert result.summary_counts() == {
        "report_snapshots": 0,
        "sales_invoices": 1,
        "purchase_invoices": 0,
        "contacts": 0,
        "ledger_accounts": 0,
        "financial_accounts": 0,
        "financial_mutations": 0,
    }
    assert client.paginated_requests[0][0] == "/admin-1/sales_invoices.json"


def test_collect_financial_mutations_uses_synchronization_batches():
    class BatchClient(FakeMoneybirdClient):
        def get_paginated(self, path, params=None):
            self.paginated_requests.append((path, params))
            return [{"id": f"mutation-{index}"} for index in range(101)]

        def post_json(self, path, json=None):
            self.post_requests.append((path, json))
            return [
                {"id": mutation_id, "amount": "1.00"} for mutation_id in json["ids"]
            ]

    client = BatchClient()

    rows = collectors.collect_financial_mutations(
        client,
        administration_id="admin-1",
        period="this_year",
        synced_at=collectors.datetime(2026, 6, 22),
    )

    assert len(rows) == 101
    assert len(client.post_requests) == 2
    assert len(client.post_requests[0][1]["ids"]) == 100
    assert len(client.post_requests[1][1]["ids"]) == 1
