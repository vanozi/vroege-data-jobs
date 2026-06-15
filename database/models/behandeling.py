# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
KlauwBehandeling model using SQLModel.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from sqlmodel import Field, SQLModel

from database.models.base import CreatedTimestampMixin, TimestampMixin


class KlauwBehandeling(CreatedTimestampMixin, TimestampMixin, SQLModel, table=True):
    """
    Database model voor klauwbehandelingen.

    Deze tabel registreert alle klauwbehandelingen die bij koeien worden uitgevoerd.
    Klauwbehandelingen zijn essentieel voor de gezondheid en mobiliteit van melkvee,
    inclusief bekappen, behandeling van infecties, en correctie van klauwproblemen.
    """

    __tablename__ = "klauw_behandelingen"
    __table_args__ = {
        "comment": "Registratie van klauwbehandelingen bij koeien, inclusief bekappen en behandeling van klauwproblemen."
    }

    # Primaire sleutel
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Unieke identificatie voor de klauwbehandeling",
        sa_column_kwargs={"comment": "Unieke identificatie voor de klauwbehandeling"},
    )

    # Koppeling naar koe
    eartag_short: str = Field(
        description="Kort oormerknummer van de koe die behandeld is - koppeling naar koeien.eartag_short",
        sa_column_kwargs={
            "comment": "Kort oormerknummer van de koe die behandeld is - koppeling naar koeien.eartag_short"
        },
    )
    animal_id: Optional[UUID] = Field(
        default=None,
        foreign_key="koeien.animal_id",
        index=True,
        description="Animal ID van de gekoppelde koe wanneer deze bepaald kon worden",
        sa_column_kwargs={
            "comment": "Animal ID van de gekoppelde koe wanneer deze bepaald kon worden"
        },
    )
    eartag: Optional[str] = Field(
        default=None,
        description="Volledig oormerknummer van de gekoppelde koe wanneer deze bepaald kon worden",
        sa_column_kwargs={
            "comment": "Volledig oormerknummer van de gekoppelde koe wanneer deze bepaald kon worden"
        },
    )

    # Behandelingsinformatie
    behandeldatum: date = Field(
        description="Datum waarop de klauwbehandeling is uitgevoerd",
        sa_column_kwargs={"comment": "Datum waarop de klauwbehandeling is uitgevoerd"},
    )

    # Aanvullende informatie
    notatie: Optional[str] = Field(
        default=None,
        description="Vrije tekst notities over de behandeling (bijv. type aandoening, actie ondernomen, medicatie)",
        sa_column_kwargs={
            "comment": "Vrije tekst notities over de behandeling (bijv. type aandoening, actie ondernomen, medicatie)"
        },
    )
