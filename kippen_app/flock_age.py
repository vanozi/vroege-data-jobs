"""Age helpers for laying hen flocks."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from database.models.laying_hens import Flock


@dataclass(frozen=True)
class BirdAge:
    """Official laying curve age in days, full weeks, and remaining days."""

    total_days: int
    weeks: int
    days: int


def calculate_bird_age(date_of_birth: date, target_date: date) -> BirdAge:
    """Return official laying curve age on a target date."""
    elapsed_days = (target_date - date_of_birth).days
    if elapsed_days < 0:
        raise ValueError("Target date cannot be before date of birth.")

    curve_day = max(elapsed_days - 1, 0)
    weeks, days = divmod(curve_day, 7)
    return BirdAge(total_days=curve_day, weeks=weeks, days=days)


def calculate_flock_age(flock: Flock, target_date: date) -> BirdAge:
    """Return flock age on a target date."""
    return calculate_bird_age(flock.date_of_birth, target_date)


def flock_age_context(
    flock: Optional[Flock],
    target_date: date,
) -> Optional[dict[str, object]]:
    """Return template/export context for a flock age."""
    if flock is None:
        return None

    age = calculate_flock_age(flock, target_date)
    return {
        "total_days": age.total_days,
        "weeks": age.weeks,
        "days": age.days,
        "label": format_bird_age(age),
    }


def format_bird_age(age: BirdAge) -> str:
    """Return a Dutch display label for a bird age."""
    return f"{age.weeks} weken en {age.days} dagen"
