"""Seed realistic demo data for the kippen dashboard.

This script is intended for local preview/testing. It creates or updates one
active flock and fills a configurable date range with realistic-looking daily
registrations for:
- eggs
- feed and water
- dead hens
- outside-nest eggs
- pallet weights

The generated series is deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlmodel import Session, delete

from database import database
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import EggPalletWeightRegistration
from database.models.laying_hens import EggPackagingWeightConfig
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.laying_hens_repository import (
    DeadHenRegistrationsRepository,
)
from database.repositories.laying_hens_repository import (
    EggPackagingWeightConfigsRepository,
)
from database.repositories.laying_hens_repository import (
    EggPalletWeightRegistrationsRepository,
)
from database.repositories.laying_hens_repository import EggRegistrationsRepository
from database.repositories.laying_hens_repository import (
    FeedWaterRegistrationsRepository,
)
from database.repositories.laying_hens_repository import FlocksRepository
from database.repositories.laying_hens_repository import FlockLayCurveNormsRepository
from database.repositories.laying_hens_repository import (
    OutsideNestEggRoundsRepository,
)

DEMO_USER = "demo-kippen-seed"
DEMO_SUPPLIER = "Demo leverancier"
DEFAULT_BREED = "Dekalb wit"
DEFAULT_FLOCK_NAME = "Demo koppel"
DEFAULT_BIRD_COUNT = 24_000


def _daterange(start_date: date, end_date: date) -> list[date]:
    return [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_decimal(value: float, *, places: int) -> Decimal:
    quant = Decimal("1").scaleb(-places)
    return Decimal(str(round(value, places))).quantize(quant)


def _weekday_label(value: date) -> str:
    return value.strftime("%A")


def _ensure_demo_packaging_config(
    config_repo: EggPackagingWeightConfigsRepository,
    start_date: date,
) -> EggPackagingWeightConfig:
    existing = config_repo.get_active_for_supplier_and_date(DEMO_SUPPLIER, start_date)
    if existing is not None:
        return existing

    return config_repo.create_packaging_weight_config(
        {
            "supplier_name": DEMO_SUPPLIER,
            "empty_packaging_weight_kg": Decimal("67.500"),
            "egg_count_per_pallet": 10800,
            "start_date": start_date,
            "end_date": None,
            "is_active": True,
            "notes": "Auto-generated for local dashboard preview.",
        }
    )


def _ensure_preview_flock(
    flock_repo: FlocksRepository,
    norm_repo: FlockLayCurveNormsRepository,
    start_date: date,
    *,
    house_id: str,
) -> tuple[int, date, int, str]:
    active_flock = flock_repo.get_current_active_flock(house_id=house_id)
    target_dob = start_date - timedelta(days=127)

    profile = None
    breed = DEFAULT_BREED
    breed_key = None
    available_breed_keys = norm_repo.list_breed_keys()
    if available_breed_keys:
        breed_key = available_breed_keys[0]
        profile = norm_repo.get_profile_by_breed_key(breed_key)

    flock_payload = {
        "flock_name": active_flock.flock_name if active_flock else DEFAULT_FLOCK_NAME,
        "flock_lay_curve_profile_id": profile.id if profile is not None else None,
        "date_of_birth": target_dob,
        "placement_date": start_date,
        "end_date": None,
        "bird_count": active_flock.bird_count if active_flock else DEFAULT_BIRD_COUNT,
        "breed": active_flock.breed or breed if active_flock else breed,
        "house_id": house_id,
        "is_active": True,
        "archived_at": None,
        "notes": "Auto-generated preview flock for kippen dashboard.",
    }

    if active_flock is None:
        flock = flock_repo.create_flock(flock_payload)
    else:
        flock = flock_repo.update_flock(active_flock.id, flock_payload)
        if flock is None:
            raise ValueError(f"Could not update active flock {active_flock.id}.")

    flock_breed_key = breed_key or "demo_profile"
    return flock.id, flock.date_of_birth, flock.bird_count, flock_breed_key


def _delete_existing_demo_rows(
    session: Session,
    *,
    flock_id: int,
    start_date: date,
    end_date: date,
) -> None:
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    session.exec(
        delete(DeadHenRegistration).where(
            DeadHenRegistration.flock_id == flock_id,
            DeadHenRegistration.registered_by == DEMO_USER,
            DeadHenRegistration.found_at >= start_dt,
            DeadHenRegistration.found_at <= end_dt,
        )
    )
    session.exec(
        delete(OutsideNestEggRound).where(
            OutsideNestEggRound.flock_id == flock_id,
            OutsideNestEggRound.registered_by == DEMO_USER,
            OutsideNestEggRound.round_at >= start_dt,
            OutsideNestEggRound.round_at <= end_dt,
        )
    )
    session.exec(
        delete(EggPalletWeightRegistration).where(
            EggPalletWeightRegistration.flock_id == flock_id,
            EggPalletWeightRegistration.created_by == DEMO_USER,
            EggPalletWeightRegistration.registration_date >= start_date,
            EggPalletWeightRegistration.registration_date <= end_date,
        )
    )


def seed_demo_data(
    *,
    days: int,
    seed: int,
    house_id: str,
    dry_run: bool = False,
) -> dict[str, int]:
    if days < 28:
        raise ValueError("Use at least 28 days so the dashboard has enough history.")

    randomizer = random.Random(seed)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    flock_repo = FlocksRepository(database.get_session)
    norm_repo = FlockLayCurveNormsRepository(database.get_session)
    egg_repo = EggRegistrationsRepository(database.get_session)
    feed_repo = FeedWaterRegistrationsRepository(database.get_session)
    dead_repo = DeadHenRegistrationsRepository(database.get_session)
    outside_repo = OutsideNestEggRoundsRepository(database.get_session)
    pallet_repo = EggPalletWeightRegistrationsRepository(database.get_session)
    config_repo = EggPackagingWeightConfigsRepository(database.get_session)

    flock_id, flock_dob, bird_count, breed_key = _ensure_preview_flock(
        flock_repo,
        norm_repo,
        start_date,
        house_id=house_id,
    )
    norm_rows = norm_repo.list_by_breed_key(breed_key)
    norms_by_week = {row.age_weeks: row for row in norm_rows}
    packaging_config = _ensure_demo_packaging_config(config_repo, start_date)

    if dry_run:
        return {
            "days": days,
            "egg_days": days,
            "feed_days": days,
            "dead_rows": days // 2,
            "outside_rows": days // 2,
            "pallet_rows": days // 4,
        }

    with Session(database.engine) as session:
        _delete_existing_demo_rows(
            session,
            flock_id=flock_id,
            start_date=start_date,
            end_date=end_date,
        )
        session.commit()

    cumulative_dead = 0
    created_dead = 0
    created_outside = 0
    created_pallets = 0

    for current_date in _daterange(start_date, end_date):
        elapsed_days = (current_date - flock_dob).days
        flock_week = max(elapsed_days - 1, 0) // 7
        norm = norms_by_week.get(flock_week)
        alive_birds = max(bird_count - cumulative_dead, 0)

        if norm is None:
            lay_pct = _clamp(92 + randomizer.uniform(-3, 2), 80, 97)
            egg_weight = 61 + randomizer.uniform(-1.2, 1.3)
            feed_per_bird = 118 + randomizer.uniform(-4, 5)
        else:
            lay_pct = _clamp(
                float(norm.lay_percentage) + randomizer.uniform(-2.5, 2.0),
                0,
                100,
            )
            egg_weight = _clamp(
                float(norm.egg_weight_grams) + randomizer.uniform(-0.9, 1.1),
                52,
                75,
            )
            feed_per_bird = _clamp(
                float(norm.feed_intake_grams_per_day) + randomizer.uniform(-3.5, 4.5),
                80,
                160,
            )

        weekend_factor = 1.01 if current_date.weekday() >= 5 else 1.0
        lay_pct = _clamp(lay_pct * weekend_factor, 0, 100)
        total_eggs = round(alive_birds * lay_pct / 100)
        second_quality_ratio = _clamp(
            0.012 + randomizer.uniform(-0.004, 0.018),
            0.005,
            0.045,
        )
        second_quality_eggs = round(total_eggs * second_quality_ratio)
        first_quality_eggs = max(total_eggs - second_quality_eggs, 0)

        feed_grams = round(alive_birds * feed_per_bird)
        water_ratio = 1.92 + randomizer.uniform(-0.18, 0.22)
        water_ml = round(feed_grams * water_ratio)

        egg_repo.upsert_egg_registration(
            {
                "house_id": house_id,
                "flock_id": flock_id,
                "registration_date": current_date,
                "weekday": _weekday_label(current_date),
                "first_quality_eggs": first_quality_eggs,
                "second_quality_eggs": second_quality_eggs,
                "total_eggs": total_eggs,
                "notes": "Auto-generated preview data.",
                "created_by": DEMO_USER,
            }
        )
        feed_repo.upsert_feed_water_registration(
            {
                "house_id": house_id,
                "flock_id": flock_id,
                "registration_date": current_date,
                "weekday": _weekday_label(current_date),
                "water_ml": water_ml,
                "feed_grams": feed_grams,
                "notes": "Auto-generated preview data.",
                "created_by": DEMO_USER,
            }
        )

        dead_count = 0
        if randomizer.random() < 0.72:
            dead_count = max(
                0,
                round(randomizer.gauss(1.4 + flock_week * 0.015, 1.1)),
            )
        if dead_count > 0:
            cumulative_dead += dead_count
            created_dead += 1
            dead_repo.create_dead_hen_registration(
                {
                    "house_id": house_id,
                    "flock_id": flock_id,
                    "found_at": datetime.combine(
                        current_date,
                        time(hour=8 + randomizer.randint(0, 4)),
                    ),
                    "count": dead_count,
                    "stable_side": randomizer.choice(["left", "right"]),
                    "section_number": randomizer.randint(1, 4),
                    "walkway": randomizer.choice(["voor", "midden", "achter"]),
                    "found_place": randomizer.choice(
                        ["onder rooster", "bij legnest", "gangpad", "hoek"]
                    ),
                    "suspected_cause": randomizer.choice(
                        ["onbekend", "pikschade", "zwak", "leggerelateerd"]
                    ),
                    "observations": "Auto-generated preview data.",
                    "registered_by": DEMO_USER,
                }
            )

        if randomizer.random() < 0.65:
            outside_count = max(
                0,
                round(total_eggs * randomizer.uniform(0.002, 0.012)),
            )
            if outside_count > 0:
                created_outside += 1
                outside_repo.create_outside_nest_egg_round(
                    {
                        "house_id": house_id,
                        "flock_id": flock_id,
                        "round_at": datetime.combine(
                            current_date,
                            time(hour=randomizer.choice([9, 11, 14, 16])),
                        ),
                        "egg_count": outside_count,
                        "notes": "Auto-generated preview data.",
                        "registered_by": DEMO_USER,
                    }
                )

        if current_date.weekday() in {1, 4}:
            created_pallets += 1
            expected_egg_mass_kg = (
                packaging_config.egg_count_per_pallet * egg_weight / 1000
            )
            pallet_weight_kg = (
                float(packaging_config.empty_packaging_weight_kg)
                + expected_egg_mass_kg
                + randomizer.uniform(-4.5, 5.5)
            )
            pallet_repo.create_pallet_weight_registration(
                {
                    "house_id": house_id,
                    "flock_id": flock_id,
                    "registration_date": current_date,
                    "weekday": _weekday_label(current_date),
                    "packaging_weight_config_id": packaging_config.id,
                    "supplier_name": packaging_config.supplier_name,
                    "pallet_weight_kg": _to_decimal(pallet_weight_kg, places=3),
                    "empty_packaging_weight_kg": packaging_config.empty_packaging_weight_kg,
                    "egg_count_per_pallet": packaging_config.egg_count_per_pallet,
                    "notes": "Auto-generated preview data.",
                    "created_by": DEMO_USER,
                }
            )

    return {
        "days": days,
        "egg_days": days,
        "feed_days": days,
        "dead_rows": created_dead,
        "outside_rows": created_outside,
        "pallet_rows": created_pallets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed realistic demo data for the kippen dashboard."
    )
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--house-id", default="main")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = seed_demo_data(
        days=args.days,
        seed=args.seed,
        house_id=args.house_id,
        dry_run=args.dry_run,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
