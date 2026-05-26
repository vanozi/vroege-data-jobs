"""Tests for laying hens repositories."""

from datetime import date, datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database.models.laying_hens import DailyLayingRegistration
from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import Flock
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.laying_hens_repository import (
    DailyLayingRegistrationsRepository,
)
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
from database.repositories.laying_hens_repository import FlocksRepository
from database.repositories.laying_hens_repository import OutsideNestEggRoundsRepository


def test_flock_repository_creates_and_lists_flocks():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))

    created = repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
            breed="Lohmann Brown",
        )
    )

    assert created.id is not None

    flocks = repository.list_flocks()
    assert len(flocks) == 1
    assert flocks[0].flock_name == "Koppel 2026"
    assert flocks[0].house_id == "main"


def test_flock_repository_finds_active_flock_for_date():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))
    repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
            bird_count=24000,
        )
    )

    active_flock = repository.get_active_flock_for_date(date(2026, 5, 26))

    assert active_flock is not None
    assert active_flock.flock_name == "Koppel 2026"
    assert repository.get_active_flock_for_date(date(2026, 4, 30)) is None
    assert repository.get_active_flock_for_date(date(2027, 1, 1)) is None


def test_flock_repository_rejects_overlapping_flock_in_same_house():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))
    repository.create_flock(
        Flock(
            flock_name="Koppel 2026 A",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
            bird_count=24000,
            house_id="main",
        )
    )

    try:
        repository.create_flock(
            Flock(
                flock_name="Koppel 2026 B",
                date_of_birth=date(2026, 2, 1),
                placement_date=date(2026, 6, 1),
                end_date=date(2027, 1, 31),
                bird_count=22000,
                house_id="main",
            )
        )
    except ValueError as exc:
        assert "overlaps" in str(exc)
    else:
        raise AssertionError("Expected overlapping same-house flock to be rejected.")


def test_flock_repository_allows_overlapping_flock_in_different_house():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))
    repository.create_flock(
        Flock(
            flock_name="House A",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
            bird_count=24000,
            house_id="main",
        )
    )

    created = repository.create_flock(
        Flock(
            flock_name="House B",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
            bird_count=20000,
            house_id="future-house",
        )
    )

    assert created.id is not None
    assert len(repository.list_flocks()) == 2


def test_flock_repository_allows_next_flock_after_previous_end_date():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))
    repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
            bird_count=24000,
        )
    )

    created = repository.create_flock(
        Flock(
            flock_name="Koppel 2027",
            date_of_birth=date(2027, 1, 1),
            placement_date=date(2027, 1, 1),
            bird_count=23000,
        )
    )

    assert created.flock_name == "Koppel 2027"


def test_flock_repository_archives_and_ends_flock():
    engine = _create_test_engine()
    repository = FlocksRepository(_session_factory(engine))
    created = repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    ended = repository.end_flock(created.id, date(2026, 12, 31))
    archived = repository.archive_flock(created.id)

    assert ended.end_date == date(2026, 12, 31)
    assert archived.archived_at is not None
    assert not archived.is_active
    assert repository.get_active_flock_for_date(date(2026, 5, 26)) is None


def test_flock_repository_delete_rejects_linked_registrations():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    daily_repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    daily_repository.upsert_daily_registration(
        DailyLayingRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            first_quality_eggs=100,
        )
    )

    try:
        flock_repository.delete_flock(flock.id)
    except ValueError as exc:
        assert "linked registrations" in str(exc)
    else:
        raise AssertionError("Expected linked flock delete to be rejected.")


def test_upsert_daily_registration_updates_existing_house_date():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    created = repository.upsert_daily_registration(
        DailyLayingRegistration(
            flock_id=flock.id,
            house_id="main",
            registration_date=registration_date,
            weekday="Dinsdag",
            first_quality_eggs=20530,
            second_quality_eggs=19,
            total_eggs=20549,
            water_ml=199000,
            feed_grams=109000,
            notes="Eerste invoer",
            created_by="admin",
        )
    )
    updated = repository.upsert_daily_registration(
        {
            "flock_id": flock.id,
            "house_id": "main",
            "registration_date": registration_date,
            "weekday": "Dinsdag",
            "first_quality_eggs": 20600,
            "second_quality_eggs": 20,
            "total_eggs": 20620,
            "water_ml": 201000,
            "feed_grams": 110000,
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
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)
    main_flock = flock_repository.create_flock(
        Flock(
            flock_name="Main koppel",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    future_house_flock = flock_repository.create_flock(
        Flock(
            flock_name="Future house koppel",
            house_id="future-house",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    repository.upsert_daily_registration(
        DailyLayingRegistration(
            flock_id=main_flock.id,
            house_id="main",
            registration_date=registration_date,
            first_quality_eggs=100,
        )
    )
    repository.upsert_daily_registration(
        DailyLayingRegistration(
            flock_id=future_house_flock.id,
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
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = DailyLayingRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    created = repository.upsert_daily_registration(
        DailyLayingRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            first_quality_eggs=100,
            second_quality_eggs=5,
            total_eggs=105,
        )
    )

    updated = repository.update_daily_registration(
        created.id,
        {
            "flock_id": flock.id,
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
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = DeadHenRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    repository.create_dead_hen_registration(
        DeadHenRegistration(
            flock_id=flock.id,
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
            flock_id=flock.id,
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
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = OutsideNestEggRoundsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    created = repository.create_outside_nest_egg_round(
        OutsideNestEggRound(
            flock_id=flock.id,
            round_at=datetime(2026, 5, 26, 9, 15),
            egg_count=12,
            notes="Ochtendronde",
            registered_by="admin",
        )
    )

    assert created.id is not None

    recent = repository.list_recent()
    assert len(recent) == 1
    assert recent[0].flock_id == flock.id
    assert recent[0].egg_count == 12


def test_outside_nest_egg_round_repository_counts_for_date():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = OutsideNestEggRoundsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    repository.create_outside_nest_egg_round(
        OutsideNestEggRound(
            flock_id=flock.id,
            round_at=datetime(2026, 5, 26, 9, 15),
            egg_count=12,
            registered_by="admin",
        )
    )
    repository.create_outside_nest_egg_round(
        OutsideNestEggRound(
            flock_id=flock.id,
            round_at=datetime(2026, 5, 26, 15, 30),
            egg_count=8,
            registered_by="admin",
        )
    )
    repository.create_outside_nest_egg_round(
        OutsideNestEggRound(
            flock_id=flock.id,
            round_at=datetime(2026, 5, 27, 9, 15),
            egg_count=4,
            registered_by="admin",
        )
    )

    assert repository.count_for_date(date(2026, 5, 26)) == 20
    assert repository.count_for_date(date(2026, 5, 27)) == 4
    assert repository.count_for_date(date(2026, 5, 28)) == 0


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
