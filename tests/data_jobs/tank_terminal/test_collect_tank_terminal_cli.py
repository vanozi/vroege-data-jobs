from argparse import Namespace
from datetime import datetime

from database.models.tank_transaction import TankTransaction
from data_jobs.tank_terminal.collectors import TankTerminalCollectionResult
from data_jobs.tank_terminal.config import TankTerminalConfig
from data_jobs.tank_terminal.scripts import collect_tank_terminal


def test_run_dry_run_prints_summary(monkeypatch, capsys):
    config = TankTerminalConfig(
        base_url="http://tank.example.test",
        username="user",
        password="password",
    )
    row = TankTransaction(
        transaction_number="001012235085",
        start_date_time=datetime(2022, 8, 23, 10, 30, 38),
        transaction_date=datetime(2022, 8, 23, 10, 30, 38).date(),
        transaction_hour="10:30:38",
        vehicle="Siloking",
        driver="Jeffrey",
        transaction_type="Dispensing",
        acquisition_mode="Normal",
        transaction_status="Normal",
        product="Diesel",
        quantity_liters=87.47,
        quantity_units="L",
        meter_value=271,
        meter_type="h",
    )
    expected_latest = datetime(2022, 8, 22, 10, 0, 0)

    class FakeRepository:
        def __init__(self):
            self.models_by_start_date_time = []

        def get_latest_start_date_time(self):
            return expected_latest

        def upsert_tank_transaction_by_start_date_time(self, model):
            self.models_by_start_date_time.append(model)

    fake_repository = FakeRepository()

    def fake_collect(config, limit, progress_callback, latest_start_date_time):
        assert latest_start_date_time == expected_latest
        return TankTerminalCollectionResult([row])

    monkeypatch.setattr(
        collect_tank_terminal.tank_terminal_config,
        "load_tank_terminal_config",
        lambda: config,
    )
    monkeypatch.setattr(
        collect_tank_terminal.collectors,
        "collect_tank_terminal_rows",
        fake_collect,
    )
    monkeypatch.setattr(
        collect_tank_terminal,
        "_build_repository",
        lambda: fake_repository,
    )

    exit_code = collect_tank_terminal.run(
        Namespace(
            limit=None,
            summary=True,
            dry_run=True,
            headless=None,
        ),
        logger=collect_tank_terminal.logging.getLogger("test"),
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "transactions=1" in output
    assert "saved_tank_transactions=1" in output
    assert "dry_run=True" in output
