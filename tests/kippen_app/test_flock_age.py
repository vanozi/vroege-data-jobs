"""Tests for flock age helpers."""

from datetime import date

import pytest

from database.models.laying_hens import Flock
from kippen_app import flock_age


def test_calculate_bird_age_returns_weeks_days_and_total_days():
    age = flock_age.calculate_bird_age(date(2025, 10, 1), date(2026, 5, 26))

    assert age.total_days == 237
    assert age.weeks == 33
    assert age.days == 6
    assert flock_age.format_bird_age(age) == "33 weken en 6 dagen"


def test_calculate_bird_age_rejects_target_before_birth():
    with pytest.raises(ValueError, match="before date of birth"):
        flock_age.calculate_bird_age(date(2026, 5, 26), date(2026, 5, 25))


def test_flock_age_context_returns_template_values():
    flock = Flock(
        flock_name="Koppel 2026",
        date_of_birth=date(2025, 10, 1),
        placement_date=date(2026, 5, 1),
        bird_count=24000,
    )

    context = flock_age.flock_age_context(flock, date(2026, 5, 26))

    assert context == {
        "total_days": 237,
        "weeks": 33,
        "days": 6,
        "label": "33 weken en 6 dagen",
    }


def test_flock_age_context_returns_none_without_flock():
    assert flock_age.flock_age_context(None, date(2026, 5, 26)) is None
