import argparse

from data_jobs.moneybird import collectors
from data_jobs.moneybird.scripts import collect_moneybird


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, *args):
        self.messages.append(args)

    def error(self, *args):
        self.messages.append(args)

    def exception(self, *args):
        self.messages.append(args)


def test_persist_rows_dry_run_returns_counts_without_repositories():
    result = collectors.MoneybirdDashboardCollectionResult(
        report_snapshots=[{"report_type": "profit_loss"}],
        sales_invoices=[{"moneybird_id": "sales-1"}],
        purchase_invoices=[{"moneybird_id": "purchase-1"}],
        contacts=[{"moneybird_id": "contact-1"}],
        ledger_accounts=[{"moneybird_id": "ledger-1"}],
        financial_accounts=[{"moneybird_id": "account-1"}],
        financial_mutations=[{"moneybird_id": "mutation-1"}],
    )

    saved_counts = collect_moneybird._persist_rows(result, dry_run=True)

    assert saved_counts == {
        "report_snapshots": 1,
        "sales_invoices": 1,
        "purchase_invoices": 1,
        "contacts": 1,
        "ledger_accounts": 1,
        "financial_accounts": 1,
        "financial_mutations": 1,
    }


def test_summary_lines_include_collected_and_saved_counts():
    result = collectors.MoneybirdDashboardCollectionResult(
        report_snapshots=[{}],
        sales_invoices=[{}, {}],
        purchase_invoices=[],
        contacts=[{}],
        ledger_accounts=[{}],
        financial_accounts=[],
        financial_mutations=[{}, {}],
    )

    lines = collect_moneybird._summary_lines(
        result,
        {
            "report_snapshots": 1,
            "sales_invoices": 2,
            "purchase_invoices": 0,
            "contacts": 1,
            "ledger_accounts": 1,
            "financial_accounts": 0,
            "financial_mutations": 2,
        },
        dry_run=True,
    )

    assert "report_snapshots=1" in lines
    assert "sales_invoices=2" in lines
    assert "saved_purchase_invoices=0" in lines
    assert "contacts=1" in lines
    assert "financial_mutations=2" in lines
    assert "saved_financial_accounts=0" in lines
    assert "dry_run=True" in lines


def test_sync_flag_prefers_cli_value():
    assert collect_moneybird._sync_flag(None, True) is True
    assert collect_moneybird._sync_flag(False, True) is False
    assert collect_moneybird._sync_flag(True, False) is True


def test_apply_cli_overrides_updates_period_and_administration():
    config = collect_moneybird.moneybird_config.MoneybirdConfig(
        access_token="token",
        administration_id="old-admin",
        default_period="this_month",
    )
    args = argparse.Namespace(
        administration_id="new-admin",
        period="this_year",
    )

    updated = collect_moneybird._apply_cli_overrides(config, args)

    assert updated.administration_id == "new-admin"
    assert updated.default_period == "this_year"


def test_run_collects_and_persists_with_one_command_path(monkeypatch):
    config = collect_moneybird.moneybird_config.MoneybirdConfig(
        access_token="token",
        administration_id="admin-1",
    )
    result = collectors.MoneybirdDashboardCollectionResult(
        report_snapshots=[{"report_type": "profit_loss"}],
        sales_invoices=[{"moneybird_id": "sales-1"}],
        purchase_invoices=[{"moneybird_id": "purchase-1"}],
        contacts=[{"moneybird_id": "contact-1"}],
        ledger_accounts=[{"moneybird_id": "ledger-1"}],
        financial_accounts=[{"moneybird_id": "account-1"}],
        financial_mutations=[{"moneybird_id": "mutation-1"}],
    )
    captured = {}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_collect(client, received_config, **kwargs):
        captured["client"] = client
        captured["config"] = received_config
        captured["kwargs"] = kwargs
        return result

    monkeypatch.setattr(
        collect_moneybird.moneybird_config,
        "load_moneybird_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "data_jobs.moneybird.api_client.build_moneybird_client",
        lambda received_config: FakeClient(),
    )
    monkeypatch.setattr(
        collect_moneybird.collectors,
        "collect_dashboard_records",
        fake_collect,
    )
    monkeypatch.setattr(
        collect_moneybird,
        "_persist_rows",
        lambda received_result, dry_run: {
            "report_snapshots": len(received_result.report_snapshots),
            "sales_invoices": len(received_result.sales_invoices),
            "purchase_invoices": len(received_result.purchase_invoices),
            "contacts": len(received_result.contacts),
            "ledger_accounts": len(received_result.ledger_accounts),
            "financial_accounts": len(received_result.financial_accounts),
            "financial_mutations": len(received_result.financial_mutations),
        },
    )
    args = argparse.Namespace(
        administration_id=None,
        period=None,
        dry_run=True,
        summary=False,
        reports=None,
        sales_invoices=None,
        purchase_invoices=None,
        contacts=None,
        ledger_accounts=None,
        financial_accounts=None,
        financial_mutations=None,
    )

    exit_code = collect_moneybird.run(args, FakeLogger())

    assert exit_code == 0
    assert captured["config"] == config
    assert captured["kwargs"]["sync_reports"] is True
    assert captured["kwargs"]["sync_sales_invoices"] is True
    assert captured["kwargs"]["sync_purchase_invoices"] is True
    assert captured["kwargs"]["sync_contacts"] is True
    assert captured["kwargs"]["sync_ledger_accounts"] is True
    assert captured["kwargs"]["sync_financial_accounts"] is True
    assert captured["kwargs"]["sync_financial_mutations"] is True
    assert isinstance(captured["kwargs"]["logger"], FakeLogger)
