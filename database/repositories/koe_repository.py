# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Repository for Koe (Cow) model with specific operations using SQLModel.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from sqlmodel import func, select, update

from database.models import Koe
from .base_repository import BaseRepository


class KoeRepository(BaseRepository[Koe]):
    """Repository for Koe model with specific operations"""

    def __init__(self, session_factory):
        super().__init__(Koe, session_factory)

    def get_by_dier_id(self, dier_id: str) -> Optional[Koe]:
        """
        Get koe by dier_id.

        Args:
            dier_id: Koe ID

        Returns:
            Koe instance or None
        """
        return self.get_by_id(dier_id, id_field="dier_id")

    def get_by_oormerk(self, oormerk: str) -> Optional[Koe]:
        """
        Get koe by ear tag.

        Args:
            oormerk: Ear tag

        Returns:
            Koe instance or None
        """
        with self.get_session() as session:
            statement = select(self.model).where(self.model.oormerk == oormerk)
            return session.exec(statement).first()

    def get_by_eartag_short_for_treatment_date(
        self,
        eartag_short: str,
        behandeldatum: date,
    ) -> Optional[Koe]:
        """
        Get the best matching koe for a Klauwscore treatment row.

        Short eartag numbers can be reused. First look up all cows with this
        short eartag. If exactly one cow exists, only use it when the treatment
        date is after its birth date. If multiple cows exist, select the cow
        with the smallest positive delta between birth date and treatment date.
        """
        koeien = self.get_by_eartag_short(eartag_short)
        return _select_koe_for_treatment_date(koeien, behandeldatum)

    def get_by_eartag_short(self, eartag_short: str) -> list[Koe]:
        """Get all koeien matching a short eartag, ignoring leading zeroes."""
        with self.get_session() as session:
            normalized_eartag_short = eartag_short.lstrip("0")
            statement = (
                select(self.model)
                .where(
                    func.ltrim(self.model.eartag_short, "0") == normalized_eartag_short
                )
                .order_by(self.model.birth_date.desc())
            )
            koeien = list(session.exec(statement).all())
            for koe in koeien:
                session.expunge(koe)

            return koeien

    def get_living_koeien(self) -> list[Koe]:
        """
        Get all living koeien (is_dood = False).

        Returns:
            List of living Koe instances
        """
        return self.get_all(filters={"is_dood": False})

    def get_current_herd_koeien(self, limit: Optional[int] = None) -> list[Koe]:
        """Get koeien that are currently part of the herd."""
        with self.get_session() as session:
            statement = (
                select(self.model)
                .where(self.model.in_current_herd.is_(True))
                .order_by(self.model.eartag_short)
            )
            if limit is not None:
                statement = statement.limit(limit)

            koeien = list(session.exec(statement).all())
            for koe in koeien:
                session.expunge(koe)

            return koeien

    def get_by_geslacht(self, geslacht: str) -> list[Koe]:
        """
        Get all koeien by gender.

        Args:
            geslacht: Gender (e.g., 'V', 'M')

        Returns:
            List of Koe instances
        """
        return self.get_all(filters={"geslacht": geslacht})

    def upsert_koe(self, koe_data: dict | Koe) -> Koe:
        """
        Insert or update koe data.

        Args:
            koe_data: Dictionary with koe data OR Koe SQLModel object

        Returns:
            Koe instance
        """
        # Convert Koe object to dict if needed
        if isinstance(koe_data, Koe):
            koe_data = koe_data.model_dump()

        # Ensure in_current_herd is set to True for animals in the API
        koe_data["in_current_herd"] = True

        return self.upsert(koe_data, unique_fields=["animal_id"])

    def mark_all_not_in_herd(self, animal_ids: list[UUID]) -> int:
        """
        Mark all koeien as not in current herd if their animal_id is not in the provided list.

        Args:
            animal_ids: List of animal IDs that ARE in the current herd

        Returns:
            Number of koeien marked as not in herd
        """
        with self.get_session() as session:
            statement = (
                update(Koe)
                .where(Koe.animal_id.not_in(animal_ids))
                .values(in_current_herd=False)
            )
            result = session.exec(statement)
            return result.rowcount


def _select_koe_for_treatment_date(
    koeien: list[Koe],
    behandeldatum: date,
) -> Optional[Koe]:
    valid_koeien = [koe for koe in koeien if koe.birth_date < behandeldatum]
    if not valid_koeien:
        return None

    return min(valid_koeien, key=lambda koe: behandeldatum - koe.birth_date)
