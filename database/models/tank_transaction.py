"""Tank Terminal transaction model."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin, TimestampMixin


class TankTransaction(CreatedTimestampMixin, TimestampMixin, SQLModel, table=True):
    """Diesel fill-up transaction collected from the Tank Terminal."""

    __tablename__ = "tank_transactions"
    __table_args__ = {
        "comment": (
            "Diesel tank terminal transactions, including machine, driver, "
            "quantity, meter reading, and transaction timestamp."
        )
    }

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_number: str = Field(
        index=True,
        sa_column_kwargs={"unique": True},
        description="Unique transaction number from the Tank Terminal.",
    )
    vehicle: Optional[str] = Field(default=None)
    driver: Optional[str] = Field(default=None)
    transaction_type: Optional[str] = Field(default=None)
    acquisition_mode: Optional[str] = Field(default=None)
    transaction_status: Optional[str] = Field(default=None)
    start_date_time: datetime = Field(index=True)
    product: Optional[str] = Field(default=None)
    quantity_liters: float
    transaction_duration_seconds: Optional[int] = Field(default=None)
    meter_value: Optional[float] = Field(default=None)
    meter_type: Optional[str] = Field(default=None)
