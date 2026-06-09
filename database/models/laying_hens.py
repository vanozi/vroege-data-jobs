"""Laying hens registration models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Column, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin


class Flock(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Production batch of laying hens in one house."""

    __tablename__ = "flocks"
    __table_args__ = (
        Index(
            "ix_flocks_house_active_dates",
            "house_id",
            "placement_date",
            "end_date",
        ),
        {
            "comment": (
                "Laying hen flocks with lifecycle metadata and active date range."
            )
        },
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    flock_name: str = Field(index=True)
    flock_lay_curve_profile_id: Optional[int] = Field(
        default=None,
        foreign_key="flock_lay_curve_profiles.id",
        index=True,
    )
    date_of_birth: date = Field(index=True)
    placement_date: date = Field(index=True)
    end_date: Optional[date] = Field(default=None, index=True)
    bird_count: int = Field(ge=0)
    breed: Optional[str] = Field(default=None)
    house_id: str = Field(default="main", index=True)
    is_active: bool = Field(default=True, index=True)
    archived_at: Optional[datetime] = Field(default=None, index=True)
    notes: Optional[str] = Field(default=None)


class EggRegistration(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Daily egg count registration for one house/flock."""

    __tablename__ = "egg_registrations"
    __table_args__ = (
        UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_egg_registrations_house_date",
        ),
        {"comment": "Daily egg count rows for first and second quality eggs."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    flock_id: Optional[int] = Field(default=None, foreign_key="flocks.id", index=True)
    registration_date: date = Field(index=True)
    weekday: Optional[str] = Field(default=None)
    first_quality_eggs: int = Field(default=0, ge=0)
    second_quality_eggs: int = Field(default=0, ge=0)
    total_eggs: int = Field(default=0, ge=0)
    notes: Optional[str] = Field(default=None)
    created_by: Optional[str] = Field(default=None)


class FeedWaterRegistration(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Daily feed and water registration for one house/flock."""

    __tablename__ = "feed_water_registrations"
    __table_args__ = (
        UniqueConstraint(
            "house_id",
            "registration_date",
            name="uq_feed_water_registrations_house_date",
        ),
        {"comment": "Daily feed and water usage rows in grams and milliliters."},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    flock_id: Optional[int] = Field(default=None, foreign_key="flocks.id", index=True)
    registration_date: date = Field(index=True)
    weekday: Optional[str] = Field(default=None)
    water_ml: int = Field(default=0, ge=0)
    feed_grams: int = Field(default=0, ge=0)
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
    flock_id: Optional[int] = Field(default=None, foreign_key="flocks.id", index=True)
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
    flock_id: Optional[int] = Field(default=None, foreign_key="flocks.id", index=True)
    round_at: datetime = Field(index=True)
    egg_count: int = Field(default=0, ge=0)
    notes: Optional[str] = Field(default=None)
    registered_by: Optional[str] = Field(default=None)


class EggPackagingWeightConfig(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Supplier packaging settings used for pallet egg weight calculations."""

    __tablename__ = "egg_packaging_weight_configs"
    __table_args__ = (
        CheckConstraint(
            "empty_packaging_weight_kg >= 0",
            name="ck_egg_packaging_weight_configs_empty_weight_non_negative",
        ),
        CheckConstraint(
            "egg_count_per_pallet > 0",
            name="ck_egg_packaging_weight_configs_egg_count_positive",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_egg_packaging_weight_configs_valid_dates",
        ),
        Index(
            "ix_egg_packaging_weight_configs_supplier_dates",
            "supplier_name",
            "start_date",
            "end_date",
            "is_active",
        ),
        {"comment": ("Supplier empty packaging weights and eggs-per-pallet settings.")},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_name: str = Field(index=True)
    empty_packaging_weight_kg: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        sa_column=Column(Numeric(10, 3), nullable=False),
    )
    egg_count_per_pallet: int = Field(default=10800, gt=0)
    start_date: date = Field(index=True)
    end_date: Optional[date] = Field(default=None, index=True)
    is_active: bool = Field(default=True, index=True)
    archived_at: Optional[datetime] = Field(default=None, index=True)
    notes: Optional[str] = Field(default=None)


class EggPalletWeightRegistration(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Pallet weight registration with calculated average egg weight."""

    __tablename__ = "egg_pallet_weight_registrations"
    __table_args__ = (
        CheckConstraint(
            "pallet_weight_kg >= 0",
            name="ck_egg_pallet_weight_registrations_pallet_weight_non_negative",
        ),
        CheckConstraint(
            "empty_packaging_weight_kg >= 0",
            name="ck_egg_pallet_weight_registrations_empty_weight_non_negative",
        ),
        CheckConstraint(
            "pallet_weight_kg >= empty_packaging_weight_kg",
            name="ck_egg_pallet_weight_registrations_pallet_above_empty",
        ),
        CheckConstraint(
            "egg_count_per_pallet > 0",
            name="ck_egg_pallet_weight_registrations_egg_count_positive",
        ),
        CheckConstraint(
            "egg_weight_grams >= 0",
            name="ck_egg_pallet_weight_registrations_egg_weight_non_negative",
        ),
        Index(
            "ix_egg_pallet_weight_registrations_house_date",
            "house_id",
            "registration_date",
        ),
        {
            "comment": (
                "Pallet weight rows with copied packaging config values and "
                "calculated average egg weight in grams."
            )
        },
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    house_id: str = Field(default="main", index=True)
    flock_id: Optional[int] = Field(default=None, foreign_key="flocks.id", index=True)
    registration_date: date = Field(index=True)
    weekday: Optional[str] = Field(default=None)
    packaging_weight_config_id: Optional[int] = Field(
        default=None,
        foreign_key="egg_packaging_weight_configs.id",
        index=True,
    )
    supplier_name: str = Field(index=True)
    pallet_weight_kg: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        sa_column=Column(Numeric(10, 3), nullable=False),
    )
    empty_packaging_weight_kg: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        sa_column=Column(Numeric(10, 3), nullable=False),
    )
    egg_count_per_pallet: int = Field(default=10800, gt=0)
    egg_weight_grams: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        sa_column=Column(Numeric(10, 4), nullable=False),
    )
    notes: Optional[str] = Field(default=None)
    created_by: Optional[str] = Field(default=None)


class FlockLayCurveNorm(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """Breed norm curve values per age week from manufacturer specifications."""

    __tablename__ = "flock_lay_curve_norms"
    __table_args__ = (
        UniqueConstraint(
            "breed_key",
            "age_weeks",
            name="uq_flock_lay_curve_norms_breed_week",
        ),
        CheckConstraint(
            "age_weeks BETWEEN 18 AND 100",
            name="ck_flock_lay_curve_norms_age_weeks_range",
        ),
        Index("ix_flock_lay_curve_norms_breed_key_week", "breed_key", "age_weeks"),
        {
            "comment": (
                "Manufacturer breed norm curve per age week. "
                "breed_key example: dekalb_white_scharrel_voliere."
            )
        },
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    flock_lay_curve_profile_id: int = Field(
        foreign_key="flock_lay_curve_profiles.id",
        index=True,
    )
    breed_key: str = Field(index=True)
    breed_name: str = Field()
    source: str = Field()
    age_weeks: int = Field(ge=18, le=100)

    # Per aanwezige hen
    lay_percentage: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 2), nullable=False),
    )
    egg_weight_grams: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 2), nullable=False),
    )
    egg_mass_grams: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 2), nullable=False),
    )
    feed_intake_grams_per_day: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(6, 2), nullable=False),
    )
    feed_conversion_ratio: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 3), nullable=False),
    )
    liveability_percentage: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 2), nullable=False),
    )
    hen_weight_grams: Optional[int] = Field(default=None)

    # Per opgezette hen (cumulatief)
    cumulative_eggs_per_placed_hen: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(7, 1), nullable=False),
    )
    cumulative_egg_kg_per_placed_hen: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(7, 2), nullable=False),
    )
    cumulative_feed_kg_per_placed_hen: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(7, 2), nullable=False),
    )
    cumulative_feed_conversion_ratio: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(5, 3), nullable=False),
    )


class FlockLayCurveProfile(
    CreatedTimestampMixin,
    SQLModel,
    table=True,
):
    """One selectable lay-curve norm profile that many flocks can reference."""

    __tablename__ = "flock_lay_curve_profiles"
    __table_args__ = (
        UniqueConstraint(
            "breed_key",
            name="uq_flock_lay_curve_profiles_breed_key",
        ),
        {"comment": ("Selectable lay-curve norm profiles that flocks can reference.")},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    breed_key: str = Field(index=True)
    breed_name: str = Field()
    source: str = Field()
