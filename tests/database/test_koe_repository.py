from datetime import date
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.models.koe import Koe
from database.repositories.koe_repository import KoeRepository


def test_get_by_eartag_short_for_treatment_date_returns_newest_valid_koe():
    engine = _create_test_engine()
    repository = KoeRepository(_session_factory(engine))
    older = _build_koe(
        UUID("12345678-1234-5678-1234-567812345678"),
        "NL111",
        date(2020, 1, 1),
    )
    newest_valid_animal_id = UUID("22345678-1234-5678-1234-567812345678")
    newest_valid = _build_koe(
        newest_valid_animal_id,
        "NL222",
        date(2024, 1, 1),
    )
    too_young = _build_koe(
        UUID("32345678-1234-5678-1234-567812345678"),
        "NL333",
        date(2026, 5, 19),
    )

    with Session(engine) as session:
        session.add(older)
        session.add(newest_valid)
        session.add(too_young)
        session.commit()

    found = repository.get_by_eartag_short_for_treatment_date(
        "101",
        date(2026, 5, 19),
    )

    assert found is not None
    assert found.animal_id == newest_valid_animal_id
    assert found.eartag == "NL222"
    assert found.birth_date == date(2024, 1, 1)


def test_get_by_eartag_short_for_treatment_date_returns_none_before_birth():
    engine = _create_test_engine()
    repository = KoeRepository(_session_factory(engine))

    with Session(engine) as session:
        session.add(
            _build_koe(
                UUID("12345678-1234-5678-1234-567812345678"),
                "NL111",
                date(2026, 5, 19),
            )
        )
        session.commit()

    found = repository.get_by_eartag_short_for_treatment_date(
        "101",
        date(2026, 5, 19),
    )

    assert found is None


def test_get_by_eartag_short_for_treatment_date_matches_without_leading_zeroes():
    engine = _create_test_engine()
    repository = KoeRepository(_session_factory(engine))
    animal_id = UUID("12345678-1234-5678-1234-567812345678")

    with Session(engine) as session:
        session.add(
            Koe(
                animalId=animal_id,
                sex="female",
                eartag="NL647304347",
                birthDate=date(2019, 4, 3),
                name="Koe",
                number=434,
                hairColor="black-white",
                eartagShort="0434",
            )
        )
        session.commit()

    found = repository.get_by_eartag_short_for_treatment_date(
        "434",
        date(2024, 10, 15),
    )

    assert found is not None
    assert found.animal_id == animal_id
    assert found.eartag_short == "0434"


def _create_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    return lambda: Session(engine)


def _build_koe(animal_id: UUID, eartag: str, birth_date: date) -> Koe:
    return Koe(
        animalId=animal_id,
        sex="female",
        eartag=eartag,
        birthDate=birth_date,
        name="Koe",
        number=101,
        hairColor="black-white",
        eartagShort="101",
    )
