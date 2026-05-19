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
    halsbandnummer: int = Field(
        description="Halsbandnummer van de koe die behandeld is - koppeling naar de koe",
        sa_column_kwargs={
            "comment": "Halsbandnummer van de koe die behandeld is - koppeling naar de koe"
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
