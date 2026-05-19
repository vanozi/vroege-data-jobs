import logging
from typing import Optional
from uuid import UUID

from database.models.koe import Koe, KoeDetail
from database.models.melking import Melking
from database.repositories.koe_detail_repository import KoeDetailRepository
from database.repositories.koe_repository import KoeRepository
from database.repositories.melkingen_repository import MelkingenRepository


def save_koeien(
    koeien: list[Koe],
    koe_repository: Optional[KoeRepository],
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert koe records and return the number of records processed."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d koeien.", len(koeien))
        return len(koeien)

    if koe_repository is None:
        raise ValueError("koe_repository is required when dry_run is False.")

    saved_count = 0
    for koe in koeien:
        koe_repository.upsert_koe(koe)
        saved_count += 1

    _log_count(logger, "Saved %d koeien.", saved_count)
    return saved_count


def save_koe_details(
    details: list[KoeDetail],
    koe_detail_repository: Optional[KoeDetailRepository],
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert koe detail records and return the number of records processed."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d koe details.", len(details))
        return len(details)

    if koe_detail_repository is None:
        raise ValueError("koe_detail_repository is required when dry_run is False.")

    saved_count = 0
    for detail in details:
        koe_detail_repository.upsert_koe_detail(detail)
        saved_count += 1

    _log_count(logger, "Saved %d koe details.", saved_count)
    return saved_count


def save_melkingen(
    melkingen: list[Melking],
    melkingen_repository: Optional[MelkingenRepository],
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert melking records and return the number of records processed."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d melkingen.", len(melkingen))
        return len(melkingen)

    if melkingen_repository is None:
        raise ValueError("melkingen_repository is required when dry_run is False.")

    saved_count = 0
    for melking in melkingen:
        melkingen_repository.upsert_melking(melking)
        saved_count += 1

    _log_count(logger, "Saved %d melkingen.", saved_count)
    return saved_count


def mark_missing_koeien_not_in_current_herd(
    current_animal_ids: list[UUID],
    koe_repository: Optional[KoeRepository],
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Mark koeien missing from the latest herd registration as no longer active."""
    if dry_run:
        _log_count(
            logger,
            "Dry run: would mark koeien outside %d current animal ids as inactive.",
            len(current_animal_ids),
        )
        return 0

    if koe_repository is None:
        raise ValueError("koe_repository is required when dry_run is False.")

    marked_count = koe_repository.mark_all_not_in_herd(current_animal_ids)
    _log_count(logger, "Marked %d koeien as not in current herd.", marked_count)
    return marked_count


def _log_count(
    logger: Optional[logging.Logger],
    message: str,
    count: int,
) -> None:
    if logger is None:
        return

    logger.info(message, count)
