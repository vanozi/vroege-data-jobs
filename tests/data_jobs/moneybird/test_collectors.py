from data_jobs.moneybird import collectors
from data_jobs.moneybird.config import MoneybirdConfig


class FakeMoneybirdClient:
    def __init__(self):
        self.json_requests = []
        self.paginated_requests = []

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
    ]


def test_collect_dashboard_records_resolves_administration_by_name():
    client = FakeMoneybirdClient()

    result = collectors.collect_dashboard_records(
        client,
        build_config(administration_id=None),
        sync_reports=False,
        sync_sales_invoices=True,
        sync_purchase_invoices=False,
    )

    assert result.summary_counts() == {
        "report_snapshots": 0,
        "sales_invoices": 1,
        "purchase_invoices": 0,
    }
    assert client.paginated_requests[0][0] == "/admin-1/sales_invoices.json"
