# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Melking (Milking) model using SQLModel.

Stores individual milking records for each cow.
"""

from datetime import date, datetime
from uuid import UUID
from sqlmodel import Field, SQLModel
from typing import Optional
from .base import CreatedTimestampMixin, TimestampMixin


class Melking(CreatedTimestampMixin, TimestampMixin, SQLModel, table=True):
    """
    Database model voor melkingen (milkings).

    Each record represents a single milking event with details like:
    - Milk yield
    - Milking speed and duration
    - Conductivity values (mastitis detection)
    - Days in milk (DIM)
    """

    __tablename__ = "melkingen"

    # Primary key
    id: UUID = Field(primary_key=True)

    # Foreign keys
    animal_id: UUID = Field(
        foreign_key="koeien.animal_id", index=True, alias="animalId"
    )

    # Timestamp and milking info
    shift_date: date = Field(index=True, alias="shiftDate")
    shift_number: int = Field(
        alias="shiftNumber"
    )  # 1, 2, 3 (morning, afternoon, evening)
    date_time: datetime = Field(index=True, alias="dateTime")
    dim: int  # Days in milk

    # Milk production
    milk: float  # Milk yield in kg
    kind: int  # Milk type/kind
    milk_speed: Optional[float] = Field(default=None, alias="milkSpeed")  # kg/min
    milk_duration: Optional[int] = Field(default=None, alias="milkDuration")  # seconds

    # Milking location
    milk_stand_no: Optional[int] = Field(default=None, alias="milkStandNo")

    # Conductivity values (mastitis detection)
    cond_value_lf: Optional[int] = Field(
        default=None, alias="condValueLf"
    )  # Left front
    cond_avg_last_21_lf: Optional[float] = Field(default=None, alias="condAvgLast21Lf")
    cond_std_dev_last_21_lf: Optional[float] = Field(
        default=None, alias="condStdDevLast21Lf"
    )

    # Attention flags (mastitis alerts)
    cond_attn_lf: bool = Field(default=False, alias="condAttnLf")  # Left front
    cond_attn_rf: bool = Field(default=False, alias="condAttnRf")  # Right front
    cond_attn_lr: bool = Field(default=False, alias="condAttnLr")  # Left rear
    cond_attn_rr: bool = Field(default=False, alias="condAttnRr")  # Right rear

    # System info
    process_computer_type: Optional[int] = Field(
        default=None, alias="processComputerType"
    )
    indicatie_alternerend: bool = Field(default=False, alias="indicatieAlternerend")
    can_edit: bool = Field(default=False, alias="canEdit")

    class Config:
        populate_by_name = True
