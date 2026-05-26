"""Laying hens registration models."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin


class DailyLayingRegistration(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Daily laying calendar registration for one house."""

    __tablename__ = "daily_laying_registrations"
    __table_args__ = (
        UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_daily_laying_registrations_house_date",
        ),
        {
            "comment": (
                "Daily laying calendar rows for egg counts, feed, water, and notes."
            )
        },
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    registration_date: date = Field(index=True)
    weekday: Optional[str] = Field(default=None)
    first_quality_eggs: int = Field(default=0, ge=0)
    second_quality_eggs: int = Field(default=0, ge=0)
    total_eggs: int = Field(default=0, ge=0)
    water_liters: Optional[float] = Field(default=None, ge=0)
    feed_kg: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None)
    created_by: Optional[str] = Field(default=None)


class DeadHenRegistration(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Detailed dead hen registration with structured location."""

    __tablename__ = "dead_hen_registrations"
    __table_args__ = {
        "comment": "Dead hen observations with stable side, section, and place."
    }

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    found_at: datetime = Field(index=True)
    count: int = Field(default=1, ge=1)
    stable_side: Optional[str] = Field(default=None)
    section_number: Optional[int] = Field(default=None, ge=1, le=4)
    walkway: Optional[str] = Field(default=None)
    found_place: Optional[str] = Field(default=None)
    suspected_cause: Optional[str] = Field(default=None)
    observations: Optional[str] = Field(default=None)
    registered_by: Optional[str] = Field(default=None)


class OutsideNestEggRound(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Outside-nest egg collection round."""

    __tablename__ = "outside_nest_egg_rounds"
    __table_args__ = {
        "comment": "Outside-nest egg collection rounds with date/time and count."
    }

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    round_at: datetime = Field(index=True)
    egg_count: int = Field(default=0, ge=0)
    notes: Optional[str] = Field(default=None)
    registered_by: Optional[str] = Field(default=None)
