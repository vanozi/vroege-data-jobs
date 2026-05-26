"""Tests for laying hens repositories."""

from datetime import date, datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.laying_hens_repository import (
    DailyLayingRegistrationsRepository,
)
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository


def test_upsert_daily_registration_updates_existing_house_date():
    engine = _create_test_engine()
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)

    created = repository.upsert_daily_registration(
        DailyLayingRegistration(
            house_id="main",
            registration_date=registration_date,
            weekday="Dinsdag",
            first_quality_eggs=20530,
            second_quality_eggs=19,
            total_eggs=20549,
            water_liters=199,
            feed_kg=109,
            notes="Eerste invoer",
            created_by="admin",
        )
    )
    updated = repository.upsert_daily_registration(
        {
            "house_id": "main",
            "registration_date": registration_date,
            "weekday": "Dinsdag",
            "first_quality_eggs": 20600,
            "second_quality_eggs": 20,
            "total_eggs": 20620,
            "water_liters": 201,
            "feed_kg": 110,
            "notes": "Gecorrigeerd",
            "created_by": "admin",
        }
    )

    assert created.id == updated.id

    with Session(engine) as session:
        registrations = session.exec(select(DailyLayingRegistration)).all()

    assert len(registrations) == 1
    assert registrations[0].first_quality_eggs == 20600
    assert registrations[0].total_eggs == 20620
    assert registrations[0].notes == "Gecorrigeerd"


def test_daily_registration_unique_key_is_per_house():
    engine = _create_test_engine()
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)

    repository.upsert_daily_registration(
        DailyLayingRegistration(
            house_id="main",
            registration_date=registration_date,
            first_quality_eggs=100,
        )
    )
    repository.upsert_daily_registration(
        DailyLayingRegistration(
            house_id="future-house",
            registration_date=registration_date,
            first_quality_eggs=200,
        )
    )

    with Session(engine) as session:
        registrations = session.exec(select(DailyLayingRegistration)).all()

    assert len(registrations) == 2


def test_update_daily_registration_updates_by_id():
    engine = _create_test_engine()
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    created = repository.upsert_daily_registration(
        DailyLayingRegistration(
            registration_date=date(2026, 5, 26),
            first_quality_eggs=100,
            second_quality_eggs=5,
            total_eggs=105,
        )
    )

    updated = repository.update_daily_registration(
        created.id,
        {
            "registration_date": date(2026, 5, 27),
            "weekday": "Woensdag",
            "first_quality_eggs": 120,
            "second_quality_eggs": 6,
            "total_eggs": 126,
        },
    )

    assert updated.id == created.id
    assert updated.registration_date == date(2026, 5, 27)
    assert updated.total_eggs == 126

    with Session(engine) as session:
        registrations = session.exec(select(DailyLayingRegistration)).all()

    assert len(registrations) == 1


def test_dead_hen_repository_counts_for_date():
    engine = _create_test_engine()
    repository = DeadHenRegistrationsRepository(_session_factory(engine))

    repository.create_dead_hen_registration(
        DeadHenRegistration(
            found_at=datetime(2026, 5, 26, 8, 30),
            count=2,
            stable_side="Albering kant",
            section_number=2,
            walkway="Midden",
            found_place="Onder de stelling",
            registered_by="admin",
        )
    )
    repository.create_dead_hen_registration(
        DeadHenRegistration(
            found_at=datetime(2026, 5, 26, 15, 0),
            count=1,
            stable_side="Ziekenboeg kant",
            section_number=4,
            walkway="Rechts",
            found_place="In het gangpad",
            registered_by="admin",
        )
    )

    assert repository.count_for_date(date(2026, 5, 26)) == 3
    assert repository.count_for_date(date(2026, 5, 27)) == 0


def test_outside_nest_egg_round_repository_creates_round():
    engine = _create_test_engine()
    repository = OutsideNestEggRoundsRepository(_session_factory(engine))

    created = repository.create_outside_nest_egg_round(
        OutsideNestEggRound(
            round_at=datetime(2026, 5, 26, 9, 15),
            egg_count=12,
            notes="Ochtendronde",
            registered_by="admin",
        )
    )

    assert created.id is not None

    recent = repository.list_recent()
    assert len(recent) == 1
    assert recent[0].egg_count == 12


def _create_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    return lambda: Session(engine, expire_on_commit=False)
