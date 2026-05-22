from argparse import Namespace
from datetime import datetime

from data_jobs.tank_terminal.collectors import TankTerminalCollectionResult
from data_jobs.tank_terminal.config import TankTerminalConfig
from data_jobs.tank_terminal.parsers import ParsedTankTransaction
from data_jobs.tank_terminal.scripts import collect_tank_terminal


def test_run_dry_run_prints_summary(monkeypatch, capsys):
    config = TankTerminalConfig(
        base_url="http://tank.example.test",
        username="user",
        password="password",
    )
    row = ParsedTankTransaction(
        vehicle="Siloking",
        driver="Jeffrey",
        transaction_type="Dispensing",
        acquisition_mode="Normal",
        transaction_status="Normal",
        start_date_time=datetime(2022, 8, 23, 10, 30, 38),
        transaction_number="001012235085",
        product="Diesel",
        quantity_liters=87.47,
        transaction_duration_seconds=67,
        meter_value=271,
        meter_type="h",
    )

    monkeypatch.setattr(
        collect_tank_terminal.tank_terminal_config,
        "load_tank_terminal_config",
        lambda: config,
    )
    monkeypatch.setattr(
        collect_tank_terminal.collectors,
        "collect_tank_terminal_rows",
        lambda config, limit, progress_callback: TankTerminalCollectionResult([row]),
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
