# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Koe (Cow) model using SQLModel.

SQLModel combines SQLAlchemy and Pydantic for type-safe database models.
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy import BigInteger
from sqlmodel import Column, Field, SQLModel, Relationship
from typing import Optional
from .base import CreatedTimestampMixin, TimestampMixin


class Koe(CreatedTimestampMixin, TimestampMixin, SQLModel,table=True):
    """
    Database model voor koeien (cows).

    Uses SQLModel which provides:
    - SQLAlchemy ORM functionality
    - Pydantic validation
    - Type hints throughout
    """
    __tablename__ = 'koeien'

    animal_id: UUID = Field(primary_key=True, alias="animalId")
    sex: str
    eartag: str = Field(index=True, unique=True)
    birth_date: datetime = Field(alias="birthDate")
    name: str
    collar_number: int = Field(alias="number")
    dam_eartag: Optional[str] = Field(default=None, alias="damEartag")
    hair_color: str = Field(alias="hairColor")
    eartag_short: str = Field(alias="eartagShort")

    # Relationships
    details: Optional["KoeDetail"] = Relationship(back_populates="koe")

    class Config:
        populate_by_name = True


class KoeDetail(SQLModel, table=True):
    """Uitgebreide dier informatie (relatief statische data)"""
    __tablename__ = "koe_details"
    
    
    animal_id: UUID = Field(
        foreign_key="koeien.animal_id",
        primary_key=True,
        alias="animalId"
    )
    
    # Identificatie
    previous_number: Optional[int] = Field(default=None, alias="previousNumber")
    transponder_number: Optional[int] = Field(default=None, alias="transponder1", sa_column=Column(BigInteger))
    
    # Groepen
    feeding_group_name: Optional[str] = Field(default=None, alias="feedingGroupName")
    feeding_group_number: Optional[int] = Field(default=None, alias="feedingGroupNumber")
    barn_group_name: Optional[str] = Field(default=None, alias="barnGroupName")
    barn_group_number: Optional[int] = Field(default=None, alias="barnGroupNumber")
    
    # Type
    animal_type: str = Field(alias="animalType")
    animal_type_text: Optional[str] = Field(default=None, alias="animalTypeText")
    herd_name: Optional[str] = Field(default=None, alias="herdName")
    last_herd_id: Optional[UUID] = Field(default=None, alias="lastHerdId")

    # Status
    status :Optional[str] = Field(alias="status")
    status_days: Optional[int] = Field(default=None, alias="statusDays")

    # Current lactation
    last_calving_date: Optional[datetime] = Field(default=None, alias="lastCalvingDate")
    expected_calving_date: Optional[datetime] = Field(default=None, alias="expectedCalvingDate")
    expected_dry_off_date:  Optional[datetime] = Field(default=None, alias="expectedDryOffDate")
    expected_calving_interval : Optional[int] = Field(default=None, alias="expectedCalvingInterval")
    last_insemination_date: Optional[datetime] = Field(default=None, alias="lastInseminationDate")
    last_insemination_days: Optional[int] = Field(default=None, alias="lastInseminationDays")
    insemination_count: Optional[int] = Field(default=None, alias="inseminationCount")
    lactation_number: Optional[int] = Field(default=None, alias="lactationNumber")
    current_dim: Optional[int] = Field(default=None, alias="daysInMilk")
    last_milk  : Optional[float] = Field(default=None, alias="lastMilk")
    lactation_total_milk: Optional[float] = Field(default=None, alias="lactionTotalMilk")

    # Boolean flags
    is_dead: bool = Field(default=False, alias="isDead")
    is_young_stock: bool = Field(default=False, alias="isYoungStock")
    to_be_culled: bool = Field(default=False, alias="toBeCulled")
    aborted: bool = Field(default=False)
    barren: bool = Field(default=False)
    is_beef: bool = Field(default=False, alias="isBeef")
    
    # Afstamming
    dam: Optional[str] = None  # Moeder naam
    sire: Optional[str] = None  # Vader naam
    breed_text: Optional[str] = Field(default=None, alias="breedText")
    
    # Overig
    age: Optional[str] = None
    long_name: Optional[str] = Field(default=None, alias="longName")
    comment: Optional[str] = None

    
    # Relationship
    koe: Optional["Koe"] = Relationship(back_populates="details")

    class Config:
        populate_by_name = True
