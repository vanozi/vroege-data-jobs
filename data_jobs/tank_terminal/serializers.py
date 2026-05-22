"""Serialization helpers for Tank Terminal CLI output."""

from data_jobs.tank_terminal.collectors import TankTerminalCollectionResult


def summary_lines(
    result: TankTerminalCollectionResult,
    saved_tank_transactions: int,
    dry_run: bool,
) -> list[str]:
    """Return stable summary lines for Tank Terminal collection."""
    counts = result.summary_counts()
    return [
        f"transactions={counts['transactions']}",
        f"deduped_transactions={counts['deduped_transactions']}",
        f"duplicate_transactions={counts['duplicate_transactions']}",
        f"saved_tank_transactions={saved_tank_transactions}",
        f"dry_run={dry_run}",
    ]
