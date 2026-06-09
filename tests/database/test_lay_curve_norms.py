"""Tests for FlockLayCurveNormsRepository and the CSV seed loader."""

from decimal import Decimal
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database.models.laying_hens import FlockLayCurveProfile
from database.repositories.laying_hens_repository import FlockLayCurveNormsRepository
from database.seeds.load_lay_curve_norms import load_norms_with_repo

_CSV_PATH = (
    Path(__file__).parent.parent.parent
    / "database"
    / "seeds"
    / "dekalb_white_norms.csv"
)
_BREED_KEY = "dekalb_white_scharrel_voliere"


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


def test_csv_loads_all_83_rows():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    count = load_norms_with_repo(_CSV_PATH, repo)

    assert count == 83
    norms = repo.list_by_breed_key(_BREED_KEY)
    assert len(norms) == 83


def test_csv_loads_weeks_18_to_100():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)
    norms = repo.list_by_breed_key(_BREED_KEY)

    weeks = [n.age_weeks for n in norms]
    assert weeks[0] == 18
    assert weeks[-1] == 100
    assert weeks == list(range(18, 101))


def test_csv_spot_check_week_33():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)
    norm = repo.get_by_breed_and_week(_BREED_KEY, 33)

    assert norm is not None
    assert norm.lay_percentage == Decimal("97.0")
    assert norm.egg_weight_grams == Decimal("59.1")
    assert norm.feed_intake_grams_per_day == Decimal("120")
    assert norm.feed_conversion_ratio == Decimal("2.09")
    assert norm.liveability_percentage == Decimal("98.8")
    assert norm.hen_weight_grams == 1645
    assert norm.cumulative_eggs_per_placed_hen == Decimal("81.6")


def test_csv_spot_check_week_80():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)
    norm = repo.get_by_breed_and_week(_BREED_KEY, 80)

    assert norm is not None
    assert norm.lay_percentage == Decimal("85.7")
    assert norm.egg_weight_grams == Decimal("63.3")
    assert norm.feed_conversion_ratio == Decimal("2.22")


def test_double_load_is_idempotent():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)
    load_norms_with_repo(_CSV_PATH, repo)

    norms = repo.list_by_breed_key(_BREED_KEY)
    assert len(norms) == 83


def test_upsert_updates_existing_row():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    repo.upsert_norm(
        {
            "breed_key": _BREED_KEY,
            "breed_name": "Test",
            "source": "test",
            "age_weeks": 33,
            "lay_percentage": Decimal("90.0"),
            "egg_weight_grams": Decimal("58.0"),
            "egg_mass_grams": Decimal("52.2"),
            "feed_intake_grams_per_day": Decimal("118"),
            "feed_conversion_ratio": Decimal("2.26"),
            "liveability_percentage": Decimal("99.0"),
            "hen_weight_grams": 1600,
            "cumulative_eggs_per_placed_hen": Decimal("80.0"),
            "cumulative_egg_kg_per_placed_hen": Decimal("4.4"),
            "cumulative_feed_kg_per_placed_hen": Decimal("10.0"),
            "cumulative_feed_conversion_ratio": Decimal("2.27"),
        }
    )
    repo.upsert_norm(
        {
            "breed_key": _BREED_KEY,
            "breed_name": "Test updated",
            "source": "test",
            "age_weeks": 33,
            "lay_percentage": Decimal("97.0"),
            "egg_weight_grams": Decimal("59.1"),
            "egg_mass_grams": Decimal("57.3"),
            "feed_intake_grams_per_day": Decimal("120"),
            "feed_conversion_ratio": Decimal("2.09"),
            "liveability_percentage": Decimal("98.8"),
            "hen_weight_grams": 1645,
            "cumulative_eggs_per_placed_hen": Decimal("81.6"),
            "cumulative_egg_kg_per_placed_hen": Decimal("4.5"),
            "cumulative_feed_kg_per_placed_hen": Decimal("10.5"),
            "cumulative_feed_conversion_ratio": Decimal("2.34"),
        }
    )

    norms = repo.list_by_breed_key(_BREED_KEY)
    assert len(norms) == 1
    assert norms[0].lay_percentage == Decimal("97.0")
    assert norms[0].breed_name == "Test updated"


def test_get_by_breed_and_week_returns_none_for_unknown():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    result = repo.get_by_breed_and_week("unknown_breed", 33)

    assert result is None


def test_list_breed_keys_returns_loaded_keys():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)
    keys = repo.list_breed_keys()

    assert _BREED_KEY in keys


def test_upsert_creates_one_profile_per_breed_key():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    load_norms_with_repo(_CSV_PATH, repo)

    with Session(engine) as session:
        profiles = list(session.exec(select(FlockLayCurveProfile)).all())

    assert len(profiles) == 1
    assert profiles[0].breed_key == _BREED_KEY


def test_dry_run_does_not_write_to_database():
    engine = _create_test_engine()
    repo = FlockLayCurveNormsRepository(_session_factory(engine))

    count = load_norms_with_repo(_CSV_PATH, repo, dry_run=True)

    assert count == 83
    norms = repo.list_by_breed_key(_BREED_KEY)
    assert len(norms) == 0
