"""Persistence helpers for laying hens registrations."""

import logging
from typing import Optional

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.laying_hens_repository import (
    DailyLayingRegistrationsRepository,
)
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository


def save_daily_laying_registration(
    registration: DailyLayingRegistration,
    repository: Optional[DailyLayingRegistrationsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Upsert a daily laying registration and return the processed count."""
    normalized_registration = _with_calculated_total_eggs(registration)

    if dry_run:
        _log_count(logger, "Dry run: would save %d daily laying registration.", 1)
        return 1

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    repository.upsert_daily_registration(normalized_registration)
    _log_count(logger, "Saved %d daily laying registration.", 1)
    return 1


def save_dead_hen_registration(
    registration: DeadHenRegistration,
    repository: Optional[DeadHenRegistrationsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Create a dead hen registration and return the processed count."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d dead hen registration.", 1)
        return 1

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    repository.create_dead_hen_registration(registration)
    _log_count(logger, "Saved %d dead hen registration.", 1)
    return 1


def save_outside_nest_egg_round(
    egg_round: OutsideNestEggRound,
    repository: Optional[OutsideNestEggRoundsRepository],
    *,
    dry_run: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Create an outside-nest egg round and return the processed count."""
    if dry_run:
        _log_count(logger, "Dry run: would save %d outside-nest egg round.", 1)
        return 1

    if repository is None:
        raise ValueError("repository is required when dry_run is False.")

    repository.create_outside_nest_egg_round(egg_round)
    _log_count(logger, "Saved %d outside-nest egg round.", 1)
    return 1


def _with_calculated_total_eggs(
    registration: DailyLayingRegistration,
) -> DailyLayingRegistration:
    data = registration.model_dump()
    data["total_eggs"] = (
        registration.first_quality_eggs + registration.second_quality_eggs
    )
    return DailyLayingRegistration.model_validate(data)


def _log_count(
    logger: Optional[logging.Logger],
    message: str,
    count: int,
) -> None:
    if logger is None:
        return

    logger.info(message, count)
