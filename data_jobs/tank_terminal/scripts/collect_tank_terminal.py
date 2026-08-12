"""CLI entrypoint for collecting Tank Terminal transactions."""

import argparse
from dataclasses import replace
import logging
from typing import Optional

from database.persistence import tank_terminal as tank_terminal_persistence
from data_jobs import logger as job_logger
from data_jobs.tank_terminal import collectors
from data_jobs.tank_terminal import config as tank_terminal_config
from data_jobs.tank_terminal import serializers
from data_jobs.tank_terminal.config import TankTerminalConfig
from data_jobs.tank_terminal.config import TankTerminalConfigError


def build_parser() -> argparse.ArgumentParser:
    """Build the Tank Terminal CLI parser."""
    parser = argparse.ArgumentParser(
        description="Collect Tank Terminal diesel transactions and persist them.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only collect the first N transaction rows after parsing.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print collection and persistence totals.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect and validate rows without writing to the database.",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run Playwright in headless mode. Use --no-headless to show browser.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Run the Tank Terminal CLI."""
    args = build_parser().parse_args(argv)
    logger = job_logger.get_job_logger(__file__, __name__)

    try:
        return run(args, logger)
    except Exception as error:
        logger.exception("Tank Terminal collection failed: %s", error)
        print(f"Tank Terminal collection failed: {error}")
        return 1


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    """Collect Tank Terminal rows and optionally persist them."""
    try:
        config = _apply_cli_overrides(
            tank_terminal_config.load_tank_terminal_config(),
            args,
        )
    except TankTerminalConfigError as error:
        logger.error("Invalid Tank Terminal configuration: %s", error)
        print(f"Invalid Tank Terminal configuration: {error}")
        return 2

    limit = args.limit if args.limit is not None else config.default_limit
    repository = _build_repository()
    latest_start_date_time = repository.get_latest_start_date_time()
    result = collectors.collect_tank_terminal_rows(
        config,
        limit=limit,
        progress_callback=logger.info,
        latest_start_date_time=latest_start_date_time,
    )
    saved_count = _persist_rows(result, repository=repository, dry_run=args.dry_run)
    _log_collection_summary(result, saved_count, dry_run=args.dry_run, logger=logger)

    if args.summary:
        print(
            "\n".join(
                serializers.summary_lines(
                    result,
                    saved_tank_transactions=saved_count,
                    dry_run=args.dry_run,
                )
            )
        )
        return 0

    for row in result.rows:
        print(row.model_dump())

    return 0


def _apply_cli_overrides(
    config: TankTerminalConfig,
    args: argparse.Namespace,
) -> TankTerminalConfig:
    values: dict[str, object] = {}
    if args.headless is not None:
        values["headless"] = args.headless

    if not values:
        return config

    return replace(config, **values)


def _persist_rows(
    result: collectors.TankTerminalCollectionResult,
    repository,
    dry_run: bool,
) -> int:
    return tank_terminal_persistence.save_tank_transaction_models_by_start_date_time(
        result.rows,
        repository,
        dry_run=dry_run,
    )


def _build_repository():
    from database import database
    from database.repositories.tank_transactions_repository import (
        TankTransactionsRepository,
    )

    return TankTransactionsRepository(database.get_session)


def _log_collection_summary(
    result: collectors.TankTerminalCollectionResult,
    saved_count: int,
    dry_run: bool,
    logger: logging.Logger,
) -> None:
    counts = result.summary_counts()
    logger.info(
        "Tank Terminal summary: transactions=%s deduped_transactions=%s "
        "duplicate_transactions=%s saved_tank_transactions=%s dry_run=%s",
        counts["transactions"],
        counts["deduped_transactions"],
        counts["duplicate_transactions"],
        saved_count,
        dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
