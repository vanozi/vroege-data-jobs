import argparse
from datetime import datetime
import logging
from typing import Optional

from database.persistence import uniform_agri as uniform_agri_persistence
from data_jobs import logger as job_logger
from data_jobs.uniform_agri import config as uniform_config
from data_jobs.uniform_agri.collectors import (
    animal_details,
    herd_registration,
    milk_recordings,
)
from data_jobs.uniform_agri.config import UniformAgriConfigError
from data_jobs.uniform_agri.services.uniform_service import UniformService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect Uniform Agri cow data and optionally persist it.",
    )
    parser.add_argument(
        "--herd-id",
        default=None,
        help="Override the configured default herd id for this run.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Registration date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--include-details",
        action="store_true",
        help="Fetch and persist actual-tab cow details.",
    )
    parser.add_argument(
        "--include-milkings",
        action="store_true",
        help="Fetch and persist milk recordings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect data and log write counts without writing to the database.",
    )
    parser.add_argument(
        "--continue-on-animal-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue when detail or milking collection fails for one animal.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of collected cows processed after filtering.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logger = job_logger.get_job_logger(__file__, __name__)

    try:
        return run(args, logger)
    except Exception as error:
        logger.exception("Uniform Agri collection failed: %s", error)
        print(f"Uniform Agri collection failed: {error}")
        return 1


def run(args: argparse.Namespace, logger: logging.Logger) -> int:
    try:
        config = uniform_config.load_uniform_config()
    except UniformAgriConfigError as error:
        logger.error("Invalid Uniform Agri configuration: %s", error)
        print(f"Invalid Uniform Agri configuration: {error}")
        return 2

    herd_id = args.herd_id or config.herd_id
    collection_date = parse_collection_date(args.date)

    service = UniformService(config=config)
    repositories = None
    if not args.dry_run:
        repositories = build_repositories()

    logger.info(
        "Starting Uniform Agri collection for herd_id=%s dry_run=%s",
        herd_id,
        args.dry_run,
    )

    herd_result = herd_registration.collect_herd_registration(
        service,
        herd_id,
        collection_date,
    )
    koeien = apply_limit(herd_result.records, args.limit)
    log_failures(logger, herd_result.failures)

    saved_koeien_count = uniform_agri_persistence.save_koeien(
        koeien,
        repositories.koe_repository if repositories else None,
        dry_run=args.dry_run,
        logger=logger,
    )
    marked_missing_count = (
        uniform_agri_persistence.mark_missing_koeien_not_in_current_herd(
            [koe.animal_id for koe in koeien],
            repositories.koe_repository if repositories else None,
            dry_run=args.dry_run,
            logger=logger,
        )
    )

    saved_detail_count = 0
    detail_failure_count = 0
    if args.include_details:
        details_result = animal_details.collect_animal_details(
            service,
            herd_id,
            koeien,
            continue_on_animal_error=args.continue_on_animal_error,
        )
        detail_failure_count = details_result.failure_count
        log_failures(logger, details_result.failures)
        saved_detail_count = uniform_agri_persistence.save_koe_details(
            details_result.records,
            repositories.koe_detail_repository if repositories else None,
            dry_run=args.dry_run,
            logger=logger,
        )

    saved_milking_count = 0
    milking_failure_count = 0
    cows_without_melkingingen = 0
    if args.include_milkings:
        milkings_result = milk_recordings.collect_milk_recordings(
            service,
            herd_id,
            koeien,
            continue_on_animal_error=args.continue_on_animal_error,
        )
        milking_failure_count = milkings_result.failure_count
        cows_without_melkingingen = milkings_result.skipped_count
        log_failures(logger, milkings_result.failures)
        saved_milking_count = uniform_agri_persistence.save_melkingen(
            milkings_result.records,
            repositories.melkingen_repository if repositories else None,
            dry_run=args.dry_run,
            logger=logger,
        )

    print_summary(
        koeien_count=len(koeien),
        saved_koeien_count=saved_koeien_count,
        marked_missing_count=marked_missing_count,
        saved_detail_count=saved_detail_count,
        detail_failure_count=detail_failure_count,
        saved_milking_count=saved_milking_count,
        milking_failure_count=milking_failure_count,
        cows_without_melkingingen=cows_without_melkingingen,
        herd_failure_count=herd_result.failure_count,
        dry_run=args.dry_run,
    )
    return 0


def parse_collection_date(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None

    return datetime.strptime(value, "%Y-%m-%d")


def apply_limit(items: list, limit: Optional[int]) -> list:
    if limit is None:
        return items

    return items[:limit]


def build_repositories():
    from types import SimpleNamespace

    from database import database
    from database.repositories.koe_detail_repository import KoeDetailRepository
    from database.repositories.koe_repository import KoeRepository
    from database.repositories.melkingen_repository import MelkingenRepository

    return SimpleNamespace(
        koe_repository=KoeRepository(database.get_session),
        koe_detail_repository=KoeDetailRepository(database.get_session),
        melkingen_repository=MelkingenRepository(database.get_session),
    )


def log_failures(logger: logging.Logger, failures: list) -> None:
    for failure in failures:
        logger.error(
            "Collection failure stage=%s animal_id=%s animal_name=%s error=%s",
            failure.stage,
            failure.animal_id,
            failure.animal_name,
            failure.error_message,
        )


def print_summary(
    koeien_count: int,
    saved_koeien_count: int,
    marked_missing_count: int,
    saved_detail_count: int,
    detail_failure_count: int,
    saved_milking_count: int,
    milking_failure_count: int,
    cows_without_melkingingen: int,
    herd_failure_count: int,
    dry_run: bool,
) -> None:
    print(f"dry_run={dry_run}")
    print(f"koeien={koeien_count}")
    print(f"saved_koeien={saved_koeien_count}")
    print(f"marked_missing_koeien={marked_missing_count}")
    print(f"saved_koe_details={saved_detail_count}")
    print(f"koe_detail_failures={detail_failure_count}")
    print(f"saved_melkingen={saved_milking_count}")
    print(f"melking_failures={milking_failure_count}")
    print(f"cows_without_melkingingen={cows_without_melkingingen}")
    print(f"herd_registration_failures={herd_failure_count}")


if __name__ == "__main__":
    raise SystemExit(main())
