import argparse
from datetime import date
from dataclasses import replace
from typing import Optional

from database import database
from database.persistence import klauwscore as klauwscore_persistence
from database.repositories.behandelingen_repository import KlauwBehandelingenRepository
from database.repositories.koe_repository import KoeRepository
from data_jobs import logger as job_logger
from data_jobs.klauwscore import collectors
from data_jobs.klauwscore import config as klauwscore_config
from data_jobs.klauwscore import serializers
from data_jobs.klauwscore.config import KlauwscoreConfig


logger = job_logger.get_job_logger(__file__)


def main() -> None:
    args = parse_args()
    config = _apply_cli_overrides(klauwscore_config.load_klauwscore_config(), args)
    limit = args.limit if args.limit is not None else config.default_limit
    existing_behandeldatums = _load_existing_behandeldatums()
    existing_pdf_hrefs = _load_existing_pdf_hrefs()

    result = collectors.collect_klauwscore_rows(
        config,
        limit=limit,
        continue_on_document_error=args.continue_on_document_error,
        progress_callback=logger.info,
        existing_behandeldatums=existing_behandeldatums,
        existing_pdf_hrefs=existing_pdf_hrefs,
    )
    saved_count = _persist_rows(result.deduped_rows, dry_run=args.dry_run)
    _log_collection_summary(result, saved_count, dry_run=args.dry_run)

    if args.summary:
        print(
            "\n".join(
                serializers.summary_lines(
                    result,
                    saved_klauw_behandelingen=saved_count,
                    dry_run=args.dry_run,
                )
            )
        )
        return

    if args.flat:
        print(serializers.serialize_flat_rows(result.rows))
        return

    print(serializers.serialize_documents(result))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Klauwscore Alle notaties PDFs and persist treatments."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only collect the first N agenda PDFs.",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Output one row per notitie instead of one grouped record per cow.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Only print collection, validation, and persistence totals.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect and validate rows without writing to the database.",
    )
    parser.add_argument(
        "--continue-on-document-error",
        action="store_true",
        help="Skip PDFs that fail download or parsing instead of aborting.",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run Playwright in headless mode. Use --no-headless to show browser.",
    )
    parser.add_argument(
        "--download-attempts",
        type=int,
        default=None,
        help="Override PDF download retry attempts.",
    )
    parser.add_argument(
        "--download-timeout-ms",
        type=int,
        default=None,
        help="Override per-attempt PDF download timeout in milliseconds.",
    )
    parser.add_argument(
        "--upsert-db",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _apply_cli_overrides(
    config: KlauwscoreConfig,
    args: argparse.Namespace,
) -> KlauwscoreConfig:
    values: dict[str, object] = {}

    if args.headless is not None:
        values["headless"] = args.headless

    if args.download_attempts is not None:
        values["download_attempts"] = args.download_attempts

    if args.download_timeout_ms is not None:
        values["download_timeout_ms"] = args.download_timeout_ms

    if not values:
        return config

    return replace(config, **values)


def _persist_rows(
    rows: list[dict[str, object]],
    dry_run: bool,
) -> int:
    repository: Optional[KlauwBehandelingenRepository] = None
    koe_repository: Optional[KoeRepository] = None
    if not dry_run:
        repository = KlauwBehandelingenRepository(database.get_session)
        koe_repository = KoeRepository(database.get_session)

    return klauwscore_persistence.save_klauw_behandelingen(
        rows,
        repository,
        koe_repository,
        dry_run=dry_run,
        logger=logger,
    )


def _load_existing_behandeldatums() -> set[date]:
    repository = KlauwBehandelingenRepository(database.get_session)
    existing_behandeldatums = repository.get_existing_behandeldatums()
    logger.info(
        "Loaded %d existing Klauwscore treatment dates from the database.",
        len(existing_behandeldatums),
    )
    return existing_behandeldatums


def _load_existing_pdf_hrefs() -> set[str]:
    repository = KlauwBehandelingenRepository(database.get_session)
    existing_pdf_hrefs = repository.get_existing_pdf_hrefs()
    logger.info(
        "Loaded %d existing Klauwscore source PDF links from the database.",
        len(existing_pdf_hrefs),
    )
    return existing_pdf_hrefs


def _load_current_herd_cows(limit: Optional[int]) -> list[dict[str, object]]:
    koe_repository = KoeRepository(database.get_session)
    koeien = koe_repository.get_current_herd_koeien(limit=limit)
    return [
        {
            "animal_id": koe.animal_id,
            "eartag": koe.eartag,
            "eartag_short": koe.eartag_short,
            "name": koe.name,
            "collar_number": koe.collar_number,
            "birth_date": koe.birth_date,
        }
        for koe in koeien
    ]


def _log_collection_summary(
    result: collectors.KlauwscoreCollectionResult,
    saved_count: int,
    dry_run: bool,
) -> None:
    counts = result.summary_counts()
    logger.info(
        "Klauwscore Alle notaties PDF summary: documents=%s cow_records=%s "
        "flat_notitie_rows=%s deduped_notitie_rows=%s duplicate_notitie_rows=%s "
        "count_mismatches=%s failures=%s "
        "saved_klauw_behandelingen=%s dry_run=%s",
        counts["documents"],
        counts["cow_records"],
        counts["notitie_rows"],
        counts["deduped_notitie_rows"],
        counts["duplicate_rows"],
        counts["count_mismatches"],
        counts["failures"],
        saved_count,
        dry_run,
    )


if __name__ == "__main__":
    main()
