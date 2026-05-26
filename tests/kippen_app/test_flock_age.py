"""Tests for flock age helpers."""

from datetime import date

import pytest

from database.models.laying_hens import Flock
from kippen_app import flock_age


def test_calculate_bird_age_returns_curve_weeks_days_and_total_days():
    age = flock_age.calculate_bird_age(date(2025, 10, 1), date(2026, 5, 26))

    assert age.total_days == 236
    assert age.weeks == 33
    assert age.days == 5
    assert flock_age.format_bird_age(age) == "33 weken en 5 dagen"


def test_calculate_bird_age_uses_official_curve_day_offset():
    age = flock_age.calculate_bird_age(date(2026, 1, 15), date(2026, 5, 26))

    assert age.total_days == 130
    assert age.weeks == 18
    assert age.days == 4
    assert flock_age.format_bird_age(age) == "18 weken en 4 dagen"


def test_calculate_bird_age_does_not_go_below_zero_on_birth_date():
    age = flock_age.calculate_bird_age(date(2026, 1, 15), date(2026, 1, 15))

    assert age.total_days == 0
    assert age.weeks == 0
    assert age.days == 0


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
        "total_days": 236,
        "weeks": 33,
        "days": 5,
        "label": "33 weken en 5 dagen",
    }


def test_flock_age_context_returns_none_without_flock():
    assert flock_age.flock_age_context(None, date(2026, 5, 26)) is None
