"""Tests for laying hens repositories."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database.models.laying_hens import DeadHenRegistration
from database.models.laying_hens import EggPackagingWeightConfig
from database.models.laying_hens import EggPalletWeightRegistration
from database.models.laying_hens import EggRegistration
from database.models.laying_hens import FeedWaterRegistration
from database.models.laying_hens import Flock
from database.models.laying_hens import OutsideNestEggRound
from database.repositories.laying_hens_repository import DeadHenRegistrationsRepository
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


def test_flock_repository_delete_rejects_split_linked_registrations():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    egg_repository = EggRegistrationsRepository(_session_factory(engine))
    feed_water_repository = FeedWaterRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    egg_repository.upsert_egg_registration(
        EggRegistration(
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

    egg_repository.delete_egg_registration(
        egg_repository.get_by_house_and_date(date(2026, 5, 26)).id
    )
    feed_water_repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            water_ml=200000,
            feed_grams=109000,
        )
    )

    try:
        flock_repository.delete_flock(flock.id)
    except ValueError as exc:
        assert "linked registrations" in str(exc)
    else:
        raise AssertionError("Expected linked flock delete to be rejected.")


def test_upsert_egg_registration_updates_existing_house_date():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = EggRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    created = repository.upsert_egg_registration(
        EggRegistration(
            flock_id=flock.id,
            house_id="main",
            registration_date=registration_date,
            weekday="Dinsdag",
            first_quality_eggs=20530,
            second_quality_eggs=19,
            total_eggs=20549,
            notes="Eerste invoer",
            created_by="admin",
        )
    )
    updated = repository.upsert_egg_registration(
        {
            "flock_id": flock.id,
            "house_id": "main",
            "registration_date": registration_date,
            "weekday": "Dinsdag",
            "first_quality_eggs": 20600,
            "second_quality_eggs": 20,
            "total_eggs": 20620,
            "notes": "Gecorrigeerd",
            "created_by": "admin",
        }
    )

    assert created.id == updated.id

    with Session(engine) as session:
        registrations = session.exec(select(EggRegistration)).all()

    assert len(registrations) == 1
    assert registrations[0].first_quality_eggs == 20600
    assert registrations[0].total_eggs == 20620
    assert registrations[0].notes == "Gecorrigeerd"


def test_egg_registration_unique_key_is_per_house():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = EggRegistrationsRepository(_session_factory(engine))
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

    repository.upsert_egg_registration(
        EggRegistration(
            flock_id=main_flock.id,
            house_id="main",
            registration_date=registration_date,
            first_quality_eggs=100,
        )
    )
    repository.upsert_egg_registration(
        EggRegistration(
            flock_id=future_house_flock.id,
            house_id="future-house",
            registration_date=registration_date,
            first_quality_eggs=200,
        )
    )

    with Session(engine) as session:
        registrations = session.exec(select(EggRegistration)).all()

    assert len(registrations) == 2


def test_update_egg_registration_updates_by_id():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = EggRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    created = repository.upsert_egg_registration(
        EggRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            first_quality_eggs=100,
            second_quality_eggs=5,
            total_eggs=105,
        )
    )

    updated = repository.update_egg_registration(
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


def test_delete_egg_registration_deletes_by_id():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = EggRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    created = repository.upsert_egg_registration(
        EggRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            first_quality_eggs=100,
        )
    )

    assert repository.delete_egg_registration(created.id)
    assert repository.get_egg_registration_by_id(created.id) is None


def test_egg_registration_requires_flock_id():
    engine = _create_test_engine()
    repository = EggRegistrationsRepository(_session_factory(engine))

    try:
        repository.upsert_egg_registration(
            EggRegistration(
                registration_date=date(2026, 5, 26),
                first_quality_eggs=100,
            )
        )
    except ValueError as exc:
        assert "requires a flock_id" in str(exc)
    else:
        raise AssertionError("Expected egg registration without flock_id to fail.")


def test_upsert_feed_water_registration_updates_existing_house_date():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = FeedWaterRegistrationsRepository(_session_factory(engine))
    registration_date = date(2026, 5, 26)
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )

    created = repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=flock.id,
            house_id="main",
            registration_date=registration_date,
            weekday="Dinsdag",
            water_ml=199000,
            feed_grams=109000,
            notes="Eerste invoer",
            created_by="admin",
        )
    )
    updated = repository.upsert_feed_water_registration(
        {
            "flock_id": flock.id,
            "house_id": "main",
            "registration_date": registration_date,
            "weekday": "Dinsdag",
            "water_ml": 201000,
            "feed_grams": 110000,
            "notes": "Gecorrigeerd",
            "created_by": "admin",
        }
    )

    assert created.id == updated.id

    with Session(engine) as session:
        registrations = session.exec(select(FeedWaterRegistration)).all()

    assert len(registrations) == 1
    assert registrations[0].water_ml == 201000
    assert registrations[0].feed_grams == 110000
    assert registrations[0].notes == "Gecorrigeerd"


def test_feed_water_registration_unique_key_is_per_house():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = FeedWaterRegistrationsRepository(_session_factory(engine))
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

    repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=main_flock.id,
            house_id="main",
            registration_date=registration_date,
            water_ml=100000,
            feed_grams=200000,
        )
    )
    repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=future_house_flock.id,
            house_id="future-house",
            registration_date=registration_date,
            water_ml=110000,
            feed_grams=210000,
        )
    )

    with Session(engine) as session:
        registrations = session.exec(select(FeedWaterRegistration)).all()

    assert len(registrations) == 2


def test_update_feed_water_registration_updates_by_id():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = FeedWaterRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    created = repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            water_ml=100000,
            feed_grams=200000,
        )
    )

    updated = repository.update_feed_water_registration(
        created.id,
        {
            "flock_id": flock.id,
            "registration_date": date(2026, 5, 27),
            "weekday": "Woensdag",
            "water_ml": 120000,
            "feed_grams": 220000,
        },
    )

    assert updated.id == created.id
    assert updated.registration_date == date(2026, 5, 27)
    assert updated.water_ml == 120000
    assert updated.feed_grams == 220000


def test_delete_feed_water_registration_deletes_by_id():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    repository = FeedWaterRegistrationsRepository(_session_factory(engine))
    flock = flock_repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )
    created = repository.upsert_feed_water_registration(
        FeedWaterRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            water_ml=100000,
            feed_grams=200000,
        )
    )

    assert repository.delete_feed_water_registration(created.id)
    assert repository.get_feed_water_registration_by_id(created.id) is None


def test_feed_water_registration_requires_flock_id():
    engine = _create_test_engine()
    repository = FeedWaterRegistrationsRepository(_session_factory(engine))

    try:
        repository.upsert_feed_water_registration(
            FeedWaterRegistration(
                registration_date=date(2026, 5, 26),
                water_ml=100000,
                feed_grams=200000,
            )
        )
    except ValueError as exc:
        assert "requires a flock_id" in str(exc)
    else:
        raise AssertionError(
            "Expected feed/water registration without flock_id to fail."
        )


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


def test_packaging_weight_config_repository_lists_active_for_date():
    engine = _create_test_engine()
    repository = EggPackagingWeightConfigsRepository(_session_factory(engine))

    created = repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            egg_count_per_pallet=10800,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
        )
    )

    active_configs = repository.list_active_for_date(date(2026, 5, 26))
    inactive_configs = repository.list_active_for_date(date(2027, 1, 1))
    fetched = repository.get_active_for_supplier_and_date(
        "Eierhandel A",
        date(2026, 5, 26),
    )

    assert created.id is not None
    assert len(active_configs) == 1
    assert not inactive_configs
    assert fetched.id == created.id
    assert fetched.egg_count_per_pallet == 10800


def test_packaging_weight_config_repository_rejects_invalid_date_range():
    engine = _create_test_engine()
    repository = EggPackagingWeightConfigsRepository(_session_factory(engine))

    try:
        repository.create_packaging_weight_config(
            EggPackagingWeightConfig(
                supplier_name="Eierhandel A",
                empty_packaging_weight_kg=Decimal("48.500"),
                start_date=date(2026, 6, 1),
                end_date=date(2026, 5, 1),
            )
        )
    except ValueError as exc:
        assert "end date" in str(exc)
    else:
        raise AssertionError("Expected invalid config date range to be rejected.")


def test_packaging_weight_config_repository_rejects_overlapping_supplier_range():
    engine = _create_test_engine()
    repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            start_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
        )
    )

    try:
        repository.create_packaging_weight_config(
            EggPackagingWeightConfig(
                supplier_name="Eierhandel A",
                empty_packaging_weight_kg=Decimal("50.000"),
                start_date=date(2026, 6, 1),
                end_date=date(2027, 1, 31),
            )
        )
    except ValueError as exc:
        assert "overlaps" in str(exc)
    else:
        raise AssertionError("Expected overlapping supplier config to be rejected.")


def test_packaging_weight_config_repository_allows_overlapping_other_supplier():
    engine = _create_test_engine()
    repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            start_date=date(2026, 5, 1),
            end_date=date(2026, 12, 31),
        )
    )

    created = repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel B",
            empty_packaging_weight_kg=Decimal("50.000"),
            start_date=date(2026, 6, 1),
            end_date=date(2027, 1, 31),
        )
    )

    assert created.id is not None
    assert len(repository.list_packaging_weight_configs()) == 2


def test_packaging_weight_config_repository_archive_hides_from_active_list():
    engine = _create_test_engine()
    repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    created = repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            start_date=date(2026, 5, 1),
        )
    )

    archived = repository.archive_packaging_weight_config(created.id)

    assert archived.archived_at is not None
    assert not archived.is_active
    assert not repository.list_active_for_date(date(2026, 5, 26))


def test_pallet_weight_registration_repository_calculates_egg_weight():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    config_repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository = EggPalletWeightRegistrationsRepository(_session_factory(engine))
    flock = _create_flock(flock_repository)
    config = _create_packaging_config(config_repository)

    created = repository.create_pallet_weight_registration(
        EggPalletWeightRegistration(
            flock_id=flock.id,
            registration_date=date(2026, 5, 26),
            weekday="Dinsdag",
            packaging_weight_config_id=config.id,
            supplier_name=config.supplier_name,
            pallet_weight_kg=Decimal("700.000"),
            empty_packaging_weight_kg=config.empty_packaging_weight_kg,
            egg_count_per_pallet=config.egg_count_per_pallet,
            created_by="admin",
        )
    )

    assert created.id is not None
    assert Decimal(str(created.egg_weight_grams)) == Decimal("60.3241")


def test_pallet_weight_registration_repository_update_recalculates_egg_weight():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    config_repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository = EggPalletWeightRegistrationsRepository(_session_factory(engine))
    flock = _create_flock(flock_repository)
    config = _create_packaging_config(config_repository)
    created = repository.create_pallet_weight_registration(
        _pallet_registration(flock.id, config)
    )

    updated = repository.update_pallet_weight_registration(
        created.id,
        {
            "flock_id": flock.id,
            "registration_date": date(2026, 5, 27),
            "packaging_weight_config_id": config.id,
            "supplier_name": config.supplier_name,
            "pallet_weight_kg": Decimal("710.000"),
            "empty_packaging_weight_kg": config.empty_packaging_weight_kg,
            "egg_count_per_pallet": config.egg_count_per_pallet,
        },
    )

    assert updated.registration_date == date(2026, 5, 27)
    assert Decimal(str(updated.egg_weight_grams)) == Decimal("61.2500")


def test_pallet_weight_registration_repository_requires_required_links():
    engine = _create_test_engine()
    repository = EggPalletWeightRegistrationsRepository(_session_factory(engine))

    try:
        repository.create_pallet_weight_registration(
            EggPalletWeightRegistration(
                registration_date=date(2026, 5, 26),
                supplier_name="Eierhandel A",
                pallet_weight_kg=Decimal("700.000"),
                empty_packaging_weight_kg=Decimal("48.500"),
            )
        )
    except ValueError as exc:
        assert "flock_id" in str(exc)
    else:
        raise AssertionError("Expected missing flock_id to be rejected.")


def test_pallet_weight_registration_repository_rejects_pallet_below_empty_weight():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    config_repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository = EggPalletWeightRegistrationsRepository(_session_factory(engine))
    flock = _create_flock(flock_repository)
    config = _create_packaging_config(config_repository)

    try:
        repository.create_pallet_weight_registration(
            EggPalletWeightRegistration(
                flock_id=flock.id,
                registration_date=date(2026, 5, 26),
                packaging_weight_config_id=config.id,
                supplier_name=config.supplier_name,
                pallet_weight_kg=Decimal("40.000"),
                empty_packaging_weight_kg=config.empty_packaging_weight_kg,
                egg_count_per_pallet=config.egg_count_per_pallet,
            )
        )
    except ValueError as exc:
        assert "Pallet weight" in str(exc)
    else:
        raise AssertionError("Expected pallet below empty weight to be rejected.")


def test_pallet_weight_registration_repository_lists_and_deletes():
    engine = _create_test_engine()
    flock_repository = FlocksRepository(_session_factory(engine))
    config_repository = EggPackagingWeightConfigsRepository(_session_factory(engine))
    repository = EggPalletWeightRegistrationsRepository(_session_factory(engine))
    flock = _create_flock(flock_repository)
    config = _create_packaging_config(config_repository)
    created = repository.create_pallet_weight_registration(
        _pallet_registration(flock.id, config)
    )
    repository.create_pallet_weight_registration(
        _pallet_registration(flock.id, config, registration_date=date(2026, 6, 2))
    )

    registrations = repository.list_between(date(2026, 5, 1), date(2026, 5, 31))

    assert len(registrations) == 1
    assert registrations[0].id == created.id
    assert repository.delete_pallet_weight_registration(created.id)
    assert repository.get_pallet_weight_registration_by_id(created.id) is None


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


def _create_flock(repository: FlocksRepository) -> Flock:
    return repository.create_flock(
        Flock(
            flock_name="Koppel 2026",
            date_of_birth=date(2026, 1, 1),
            placement_date=date(2026, 5, 1),
            bird_count=24000,
        )
    )


def _create_packaging_config(
    repository: EggPackagingWeightConfigsRepository,
) -> EggPackagingWeightConfig:
    return repository.create_packaging_weight_config(
        EggPackagingWeightConfig(
            supplier_name="Eierhandel A",
            empty_packaging_weight_kg=Decimal("48.500"),
            egg_count_per_pallet=10800,
            start_date=date(2026, 5, 1),
        )
    )


def _pallet_registration(
    flock_id: int,
    config: EggPackagingWeightConfig,
    *,
    registration_date: date = date(2026, 5, 26),
) -> EggPalletWeightRegistration:
    return EggPalletWeightRegistration(
        flock_id=flock_id,
        registration_date=registration_date,
        packaging_weight_config_id=config.id,
        supplier_name=config.supplier_name,
        pallet_weight_kg=Decimal("700.000"),
        empty_packaging_weight_kg=config.empty_packaging_weight_kg,
        egg_count_per_pallet=config.egg_count_per_pallet,
        created_by="admin",
    )
