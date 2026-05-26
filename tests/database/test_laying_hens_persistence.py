"""Tests for laying hens persistence helpers."""

from datetime import date, datetime
import logging

import pytest

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import OutsideNestEggRound
from database.persistence import laying_hens


class FakeDailyLayingRegistrationsRepository:
    def __init__(self):
        self.saved_items = []

    def upsert_daily_registration(self, item):
        self.saved_items.append(item)


class FakeDeadHenRegistrationsRepository:
    def __init__(self):
        self.saved_items = []

    def create_dead_hen_registration(self, item):
        self.saved_items.append(item)


class FakeOutsideNestEggRoundsRepository:
    def __init__(self):
        self.saved_items = []

    def create_outside_nest_egg_round(self, item):
        self.saved_items.append(item)


def test_save_daily_laying_registration_calculates_total_and_logs(caplog):
    repository = FakeDailyLayingRegistrationsRepository()
    logger = logging.getLogger("test_save_daily_laying_registration")
    registration = DailyLayingRegistration(
        flock_id=1,
        registration_date=date(2026, 5, 26),
        first_quality_eggs=20530,
        second_quality_eggs=19,
        total_eggs=0,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        saved_count = laying_hens.save_daily_laying_registration(
            registration,
            repository,
            logger=logger,
        )

    assert saved_count == 1
    assert repository.saved_items[0].total_eggs == 20549
    assert "Saved 1 daily laying registration." in caplog.text


def test_save_daily_laying_registration_dry_run_skips_writes():
    repository = FakeDailyLayingRegistrationsRepository()

    saved_count = laying_hens.save_daily_laying_registration(
        DailyLayingRegistration(flock_id=1, registration_date=date(2026, 5, 26)),
        repository,
        dry_run=True,
    )

    assert saved_count == 1
    assert repository.saved_items == []


def test_save_daily_laying_registration_requires_repository():
    with pytest.raises(ValueError, match="repository is required"):
        laying_hens.save_daily_laying_registration(
            DailyLayingRegistration(flock_id=1, registration_date=date(2026, 5, 26)),
            None,
        )


def test_save_dead_hen_registration_creates_row():
    repository = FakeDeadHenRegistrationsRepository()
    registration = DeadHenRegistration(
        flock_id=1,
        found_at=datetime(2026, 5, 26, 8, 30),
        count=1,
    )

    saved_count = laying_hens.save_dead_hen_registration(
        registration,
        repository,
    )

    assert saved_count == 1
    assert repository.saved_items == [registration]


def test_save_outside_nest_egg_round_creates_row():
    repository = FakeOutsideNestEggRoundsRepository()
    egg_round = OutsideNestEggRound(
        flock_id=1,
        round_at=datetime(2026, 5, 26, 9, 15),
        egg_count=12,
    )

    saved_count = laying_hens.save_outside_nest_egg_round(
        egg_round,
        repository,
    )

    assert saved_count == 1
    assert repository.saved_items == [egg_round]
