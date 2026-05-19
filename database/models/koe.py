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

from datetime import date
from uuid import UUID
from sqlalchemy import BigInteger
from sqlmodel import Column, Field, SQLModel, Relationship
from typing import Optional
from .base import CreatedTimestampMixin, TimestampMixin


class Koe(CreatedTimestampMixin, TimestampMixin, SQLModel, table=True):
    """
    Database model voor koeien (cows).

    Deze tabel bevat de kerngegevens van alle koeien in het bedrijf.
    Uitgebreide informatie zoals gewicht, lactaties en gezondheidsdata
    worden opgeslagen in de gekoppelde KoeDetail tabel.

    """

    __tablename__ = "koeien"
    __table_args__ = {
        "comment": "Kerngegevens van alle koeien in het bedrijf. Uitgebreide informatie wordt opgeslagen in koe_details tabel."
    }

    # Unieke identificatie van het dier
    animal_id: UUID = Field(
        primary_key=True,
        alias="animalId",
        description="Unieke UUID voor identificatie van de koe in het systeem",
        sa_column_kwargs={
            "comment": "Unieke UUID voor identificatie van de koe in het systeem"
        },
    )

    # Basisgegevens
    sex: str = Field(
        description="Geslacht van het dier (bijv. 'female', 'male')",
        sa_column_kwargs={"comment": "Geslacht van het dier (bijv. 'female', 'male')"},
    )
    eartag: str = Field(
        index=True,
        unique=True,
        description="Oormerknummer - officiële unieke identificatie volgens I&R",
        sa_column_kwargs={
            "comment": "Oormerknummer - officiële unieke identificatie volgens I&R"
        },
    )
    birth_date: date = Field(
        alias="birthDate",
        description="Geboortedatum van de koe",
        sa_column_kwargs={"comment": "Geboortedatum van de koe"},
    )
    name: str = Field(
        description="Naam van de koe", sa_column_kwargs={"comment": "Naam van de koe"}
    )
    collar_number: int = Field(
        alias="number",
        description="Halsbandnummer van de koe voor makkelijke herkenning in de stal",
        sa_column_kwargs={
            "comment": "Halsbandnummer van de koe voor makkelijke herkenning in de stal"
        },
    )

    # Afstammingsgegevens
    dam_eartag: Optional[str] = Field(
        default=None,
        alias="damEartag",
        description="Oormerknummer van de moederkoe (dam)",
        sa_column_kwargs={"comment": "Oormerknummer van de moederkoe (dam)"},
    )

    # Fysieke kenmerken
    hair_color: str = Field(
        alias="hairColor",
        description="Vachtkleur van de koe",
        sa_column_kwargs={"comment": "Vachtkleur van de koe"},
    )
    eartag_short: str = Field(
        alias="eartagShort",
        description="Verkorte versie van het oormerknummer voor eenvoudige weergave",
        sa_column_kwargs={
            "comment": "Verkorte versie van het oormerknummer voor eenvoudige weergave"
        },
    )

    # Status
    in_current_herd: bool = Field(
        default=True,
        description="Indicator of de koe nog actief in de huidige kudde aanwezig is",
        sa_column_kwargs={
            "comment": "Indicator of de koe nog actief in de huidige kudde aanwezig is"
        },
    )

    # Relaties
    # De 'details' relatie bevat uitgebreide informatie
    details: Optional["KoeDetail"] = Relationship(back_populates="koe")

    class Config:
        populate_by_name = True


class KoeDetail(SQLModel, table=True):
    """
    Uitgebreide dier informatie (relatief statische data).

    Deze tabel bevat aanvullende en meer gedetailleerde informatie over koeien,
    zoals lactatie-gegevens, inseminatie, groepsindeling, en fokkerijinformatie.
    Wordt gekoppeld aan de Koe tabel via animal_id.
    """

    __tablename__ = "koe_details"
    __table_args__ = {
        "comment": "Uitgebreide koe-informatie zoals lactatie, inseminatie, groepsindeling en fokkerijgegevens. Gekoppeld aan koeien tabel."
    }

    # Primaire sleutel & relatie naar hoofdtabel
    animal_id: UUID = Field(
        foreign_key="koeien.animal_id",
        primary_key=True,
        alias="animalId",
        description="Foreign key naar de koeien tabel - unieke identificatie",
        sa_column_kwargs={
            "comment": "Foreign key naar de koeien tabel - unieke identificatie"
        },
    )

    # Identificatie - Alternatieve nummers en tracking
    previous_number: Optional[int] = Field(
        default=None,
        alias="previousNumber",
        description="Vorig halsbandnummer voordat de koe een nieuw nummer kreeg",
        sa_column_kwargs={
            "comment": "Vorig halsbandnummer voordat de koe een nieuw nummer kreeg"
        },
    )
    transponder_number: Optional[int] = Field(
        default=None,
        alias="transponder1",
        sa_column=Column(
            BigInteger,
            comment="Transponder/chip nummer voor elektronische identificatie",
        ),
        description="Transponder/chip nummer voor elektronische identificatie",
    )

    # Groepen - Indeling binnen het bedrijf
    feeding_group_name: Optional[str] = Field(
        default=None,
        alias="feedingGroupName",
        description="Naam van de voedergroep waarin de koe is ingedeeld",
        sa_column_kwargs={
            "comment": "Naam van de voedergroep waarin de koe is ingedeeld"
        },
    )
    feeding_group_number: Optional[int] = Field(
        default=None,
        alias="feedingGroupNumber",
        description="Nummer van de voedergroep",
        sa_column_kwargs={"comment": "Nummer van de voedergroep"},
    )
    barn_group_name: Optional[str] = Field(
        default=None,
        alias="barnGroupName",
        description="Naam van de stalgroep waarin de koe verblijft",
        sa_column_kwargs={"comment": "Naam van de stalgroep waarin de koe verblijft"},
    )
    barn_group_number: Optional[int] = Field(
        default=None,
        alias="barnGroupNumber",
        description="Nummer van de stalgroep",
        sa_column_kwargs={"comment": "Nummer van de stalgroep"},
    )

    # Type - Classificatie van het dier
    animal_type: str = Field(
        alias="animalType",
        description="Type dier (bijv. melkkoe, pink, kalf)",
        sa_column_kwargs={"comment": "Type dier (bijv. melkkoe, pink, kalf)"},
    )
    animal_type_text: Optional[str] = Field(
        default=None,
        alias="animalTypeText",
        description="Tekstuele omschrijving van het diertype",
        sa_column_kwargs={"comment": "Tekstuele omschrijving van het diertype"},
    )
    herd_name: Optional[str] = Field(
        default=None,
        alias="herdName",
        description="Naam van de kudde waartoe de koe behoort",
        sa_column_kwargs={"comment": "Naam van de kudde waartoe de koe behoort"},
    )
    last_herd_id: Optional[UUID] = Field(
        default=None,
        alias="lastHerdId",
        description="ID van de laatste kudde waarin de koe was ingedeeld",
        sa_column_kwargs={
            "comment": "ID van de laatste kudde waarin de koe was ingedeeld"
        },
    )

    # Status - Huidige toestand van het dier
    status: Optional[str] = Field(
        default=None,
        alias="status",
        description="Huidige status (bijv. droog, lactatie, gust, drachtig)",
        sa_column_kwargs={
            "comment": "Huidige status (bijv. droog, lactatie, gust, drachtig)"
        },
    )
    status_days: Optional[int] = Field(
        default=None,
        alias="statusDays",
        description="Aantal dagen in de huidige status",
        sa_column_kwargs={"comment": "Aantal dagen in de huidige status"},
    )

    # Lactatie - Melkproductie en voortplanting
    last_calving_date: Optional[date] = Field(
        default=None,
        alias="lastCalvingDate",
        description="Datum van de laatste afkalving",
        sa_column_kwargs={"comment": "Datum van de laatste afkalving"},
    )
    expected_calving_date: Optional[date] = Field(
        default=None,
        alias="expectedCalvingDate",
        description="Verwachte datum van de volgende afkalving",
        sa_column_kwargs={"comment": "Verwachte datum van de volgende afkalving"},
    )
    expected_dry_off_date: Optional[date] = Field(
        default=None,
        alias="expectedDryOffDate",
        description="Verwachte droogzetdatum",
        sa_column_kwargs={"comment": "Verwachte droogzetdatum"},
    )
    expected_calving_interval: Optional[int] = Field(
        default=None,
        alias="expectedCalvingInterval",
        description="Verwachte tussenkalftijd in dagen",
        sa_column_kwargs={"comment": "Verwachte tussenkalftijd in dagen"},
    )
    last_insemination_date: Optional[date] = Field(
        default=None,
        alias="lastInseminationDate",
        description="Datum van de laatste inseminatie/dekking",
        sa_column_kwargs={"comment": "Datum van de laatste inseminatie/dekking"},
    )
    last_insemination_days: Optional[int] = Field(
        default=None,
        alias="lastInseminationDays",
        description="Aantal dagen sinds de laatste inseminatie",
        sa_column_kwargs={"comment": "Aantal dagen sinds de laatste inseminatie"},
    )
    insemination_count: Optional[int] = Field(
        default=None,
        alias="inseminationCount",
        description="Aantal inseminaties in de huidige lactatie",
        sa_column_kwargs={"comment": "Aantal inseminaties in de huidige lactatie"},
    )
    lactation_number: Optional[int] = Field(
        default=None,
        alias="lactationNumber",
        description="Lactatienummer (1 = eerste lactatie, 2 = tweede, etc.)",
        sa_column_kwargs={
            "comment": "Lactatienummer (1 = eerste lactatie, 2 = tweede, etc.)"
        },
    )
    current_dim: Optional[int] = Field(
        default=None,
        alias="daysInMilk",
        description="Days In Milk - aantal dagen in lactatie",
        sa_column_kwargs={"comment": "Days In Milk - aantal dagen in lactatie"},
    )
    last_milk: Optional[float] = Field(
        default=None,
        alias="lastMilk",
        description="Laatste melkgift in kg",
        sa_column_kwargs={"comment": "Laatste melkgift in kg"},
    )
    lactation_total_milk: Optional[float] = Field(
        default=None,
        alias="lactionTotalMilk",
        description="Totale melkproductie in de huidige lactatie in kg",
        sa_column_kwargs={
            "comment": "Totale melkproductie in de huidige lactatie in kg"
        },
    )

    # Status indicatoren - Boolean vlaggen
    is_dead: bool = Field(
        default=False,
        alias="isDead",
        description="Indicator of het dier is overleden",
        sa_column_kwargs={"comment": "Indicator of het dier is overleden"},
    )
    is_young_stock: bool = Field(
        default=False,
        alias="isYoungStock",
        description="Indicator of het jongvee betreft (nog niet afgekalfd)",
        sa_column_kwargs={
            "comment": "Indicator of het jongvee betreft (nog niet afgekalfd)"
        },
    )
    to_be_culled: bool = Field(
        default=False,
        alias="toBeCulled",
        description="Indicator of de koe is gemarkeerd voor selectie/afvoer",
        sa_column_kwargs={
            "comment": "Indicator of de koe is gemarkeerd voor selectie/afvoer"
        },
    )
    aborted: bool = Field(
        default=False,
        description="Indicator of de koe heeft geaborteerd in de huidige dracht",
        sa_column_kwargs={
            "comment": "Indicator of de koe heeft geaborteerd in de huidige dracht"
        },
    )
    barren: bool = Field(
        default=False,
        description="Indicator of de koe gust is (niet drachtig)",
        sa_column_kwargs={"comment": "Indicator of de koe gust is (niet drachtig)"},
    )
    is_beef: bool = Field(
        default=False,
        alias="isBeef",
        description="Indicator of het een vleeskoe betreft (niet melk)",
        sa_column_kwargs={
            "comment": "Indicator of het een vleeskoe betreft (niet melk)"
        },
    )

    # Afstamming - Fokkerijinformatie
    dam: Optional[str] = Field(
        default=None,
        description="Naam van de moederkoe",
        sa_column_kwargs={"comment": "Naam van de moederkoe"},
    )
    sire: Optional[str] = Field(
        default=None,
        description="Naam van de vaderstier",
        sa_column_kwargs={"comment": "Naam van de vaderstier"},
    )
    breed_text: Optional[str] = Field(
        default=None,
        alias="breedText",
        description="Rasomschrijving (bijv. Holstein-Friesian, MRIJ)",
        sa_column_kwargs={"comment": "Rasomschrijving (bijv. Holstein-Friesian, MRIJ)"},
    )

    # Overig - Aanvullende informatie
    age: Optional[str] = Field(
        default=None,
        description="Leeftijd van de koe (tekstueel)",
        sa_column_kwargs={"comment": "Leeftijd van de koe (tekstueel)"},
    )
    long_name: Optional[str] = Field(
        default=None,
        alias="longName",
        description="Volledige/officiële naam van de koe",
        sa_column_kwargs={"comment": "Volledige/officiële naam van de koe"},
    )
    comment: Optional[str] = Field(
        default=None,
        description="Vrije tekst opmerkingen over de koe",
        sa_column_kwargs={"comment": "Vrije tekst opmerkingen over de koe"},
    )

    # Relatie terug naar de hoofdtabel
    koe: Optional["Koe"] = Relationship(back_populates="details")

    class Config:
        populate_by_name = True
