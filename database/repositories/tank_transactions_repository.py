"""Repository for Tank Terminal transactions."""

from datetime import datetime
from typing import Optional, Union

from sqlalchemy import func
from sqlmodel import select

from database.models.tank_transaction import TankTransaction
from database.repositories.base_repository import BaseRepository


class TankTransactionsRepository(BaseRepository[TankTransaction]):
    """Repository for TankTransaction model with transaction-number upserts."""

    def __init__(self, session_factory):
        super().__init__(TankTransaction, session_factory)

    def upsert_tank_transaction(
        self,
        tank_transaction_data: Union[dict[str, object], TankTransaction],
    ) -> TankTransaction:
        """Insert or update a Tank Terminal transaction by transaction number."""
        if isinstance(tank_transaction_data, TankTransaction):
            tank_transaction_data = tank_transaction_data.model_dump()

        return self.upsert(
            tank_transaction_data,
            unique_fields=["transaction_number"],
        )

    def upsert_tank_transaction_by_start_date_time(
        self,
        tank_transaction_data: Union[dict[str, object], TankTransaction],
    ) -> TankTransaction:
        """Insert or update a Tank Terminal transaction by start date-time."""
        if isinstance(tank_transaction_data, TankTransaction):
            tank_transaction_data = tank_transaction_data.model_dump()

        return self.upsert(
            tank_transaction_data,
            unique_fields=["start_date_time"],
        )

    def get_latest_start_date_time(self) -> Optional[datetime]:
        """Return the latest stored Tank Terminal transaction timestamp."""
        with self.get_session() as session:
            statement = select(func.max(TankTransaction.start_date_time))
            return session.exec(statement).one()
