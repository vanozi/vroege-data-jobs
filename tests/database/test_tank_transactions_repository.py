from datetime import datetime

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database.repositories.tank_transactions_repository import (
    TankTransactionsRepository,
)


def test_get_latest_start_date_time_returns_none_when_empty():
    engine = _create_engine()
    repository = TankTransactionsRepository(_session_factory(engine))

    latest = repository.get_latest_start_date_time()

    assert latest is None


def test_get_latest_start_date_time_returns_maximum_timestamp():
    engine = _create_engine()
    repository = TankTransactionsRepository(_session_factory(engine))

    repository.upsert_tank_transaction(
        _transaction("001", datetime(2026, 8, 4, 9, 30, 0))
    )
    repository.upsert_tank_transaction(
        _transaction("002", datetime(2026, 8, 6, 7, 15, 0))
    )
    repository.upsert_tank_transaction(
        _transaction("003", datetime(2026, 8, 5, 18, 45, 0))
    )

    latest = repository.get_latest_start_date_time()

    assert latest == datetime(2026, 8, 6, 7, 15, 0)


def _transaction(
    transaction_number: str, start_date_time: datetime
) -> dict[str, object]:
    return {
        "transaction_number": transaction_number,
        "start_date_time": start_date_time,
        "quantity_liters": 10.0,
    }


def _create_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _session_factory(engine):
    def factory():
        return Session(engine)

    return factory
