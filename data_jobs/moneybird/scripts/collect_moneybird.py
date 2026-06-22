"""CLI entrypoint for collecting Moneybird dashboard data."""

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import logging
from typing import Optional

from data_jobs import logger as job_logger
from data_jobs.moneybird import collectors
from data_jobs.moneybird import config as moneybird_config
from data_jobs.moneybird.config import MoneybirdConfig
from data_jobs.moneybird.exceptions import MoneybirdConfigError
from database.persistence import moneybird as moneybird_persistence


def build_parser() -> argparse.ArgumentParser:
    """Build the Moneybird CLI parser."""
    parser = argparse.ArgumentParser(
        description="Collect Moneybird reports and invoices and persist them.",
    )
    parser.add_argument(
        "--administration-id",
        default=None,
        help="Moneybird administration ID. Defaults to MONEYBIRD_ADMINISTRATION_ID.",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Moneybird period filter. Defaults to MONEYBIRD_DEFAULT_PERIOD.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect and transform rows without writing to the database.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print collection and persistence totals.",
    )
    parser.add_argument(
        "--reports",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Collect profit/loss and balance sheet report snapshots.",
    )
    parser.add_argument(
        "--sales-invoices",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Collect sales invoices.",
    )
    parser.add_argument(
        "--purchase-invoices",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Collect purchase invoices.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Run the Moneybird CLI."""
    args = build_parser().parse_args(argv)
    logger = job_logger.get_job_logger(__file__, __name__)

    try:
        return run(args, logger)
    except Exception as error:
        logger.exception("Moneybird collection failed: %s", error)
        print(f"Moneybird collection failed: {error}")
        return 1


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    """Collect Moneybird dashboard-critical rows and optionally persist them."""
    try:
        config = _apply_cli_overrides(moneybird_config.load_moneybird_config(), args)
    except MoneybirdConfigError as error:
        logger.error("Invalid Moneybird configuration: %s", error)
        print(f"Invalid Moneybird configuration: {error}")
        return 2

    from data_jobs.moneybird.api_client import build_moneybird_client

    with build_moneybird_client(config) as client:
        result = collectors.collect_dashboard_records(
            client,
            config,
            administration_id=args.administration_id,
            period=args.period,
            sync_reports=_sync_flag(args.reports, config.sync_reports),
            sync_sales_invoices=_sync_flag(args.sales_invoices, config.sync_invoices),
            sync_purchase_invoices=_sync_flag(
                args.purchase_invoices,
                config.sync_invoices,
            ),
        )

    saved_counts = _persist_rows(result, dry_run=args.dry_run)
    _log_collection_summary(result, saved_counts, args.dry_run, logger)

    if args.summary:
        for line in _summary_lines(result, saved_counts, args.dry_run):
            print(line)

    return 0


def _apply_cli_overrides(
    config: MoneybirdConfig,
    args: argparse.Namespace,
) -> MoneybirdConfig:
    values: dict[str, object] = {}
    if args.period:
        values["default_period"] = args.period
    if args.administration_id:
        values["administration_id"] = args.administration_id

    if not values:
        return config

    return replace(config, **values)


def _sync_flag(cli_value: Optional[bool], config_value: bool) -> bool:
    if cli_value is None:
        return config_value

    return cli_value


def _persist_rows(
    result: collectors.MoneybirdDashboardCollectionResult,
    *,
    dry_run: bool,
) -> dict[str, int]:
    repositories = _build_repositories() if not dry_run else {}
    return {
        "report_snapshots": moneybird_persistence.save_moneybird_report_snapshots(
            result.report_snapshots,
            repositories.get("report_snapshots"),
            dry_run=dry_run,
        ),
        "sales_invoices": moneybird_persistence.save_moneybird_sales_invoices(
            result.sales_invoices,
            repositories.get("sales_invoices"),
            dry_run=dry_run,
        ),
        "purchase_invoices": moneybird_persistence.save_moneybird_purchase_invoices(
            result.purchase_invoices,
            repositories.get("purchase_invoices"),
            dry_run=dry_run,
        ),
    }


def _build_repositories() -> dict[str, object]:
    from database import database
    from database.repositories.moneybird_repository import (
        MoneybirdPurchaseInvoicesRepository,
        MoneybirdReportSnapshotsRepository,
        MoneybirdSalesInvoicesRepository,
    )

    return {
        "report_snapshots": MoneybirdReportSnapshotsRepository(database.get_session),
        "sales_invoices": MoneybirdSalesInvoicesRepository(database.get_session),
        "purchase_invoices": MoneybirdPurchaseInvoicesRepository(database.get_session),
    }


def _log_collection_summary(
    result: collectors.MoneybirdDashboardCollectionResult,
    saved_counts: dict[str, int],
    dry_run: bool,
    logger: logging.Logger,
) -> None:
    counts = result.summary_counts()
    logger.info(
        "Moneybird summary: report_snapshots=%s sales_invoices=%s "
        "purchase_invoices=%s saved_report_snapshots=%s saved_sales_invoices=%s "
        "saved_purchase_invoices=%s dry_run=%s",
        counts["report_snapshots"],
        counts["sales_invoices"],
        counts["purchase_invoices"],
        saved_counts["report_snapshots"],
        saved_counts["sales_invoices"],
        saved_counts["purchase_invoices"],
        dry_run,
    )


def _summary_lines(
    result: collectors.MoneybirdDashboardCollectionResult,
    saved_counts: dict[str, int],
    dry_run: bool,
) -> list[str]:
    counts = result.summary_counts()
    return [
        f"report_snapshots={counts['report_snapshots']}",
        f"sales_invoices={counts['sales_invoices']}",
        f"purchase_invoices={counts['purchase_invoices']}",
        f"saved_report_snapshots={saved_counts['report_snapshots']}",
        f"saved_sales_invoices={saved_counts['sales_invoices']}",
        f"saved_purchase_invoices={saved_counts['purchase_invoices']}",
        f"dry_run={dry_run}",
        f"finished_at={datetime.now(UTC).isoformat()}",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
