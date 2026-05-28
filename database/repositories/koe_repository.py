# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Repository for Koe (Cow) model with specific operations using SQLModel.
"""

from typing import Optional, List, Union
from uuid import UUID
from sqlmodel import select, update
from .base_repository import BaseRepository
from database.models import Koe


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

    def get_living_koeien(self) -> List[Koe]:
        """
        Get all living koeien (is_dood = False).

        Returns:
            List of living Koe instances
        """
        return self.get_all(filters={"is_dood": False})

    def get_by_geslacht(self, geslacht: str) -> List[Koe]:
        """
        Get all koeien by gender.

        Args:
            geslacht: Gender (e.g., 'V', 'M')

        Returns:
            List of Koe instances
        """
        return self.get_all(filters={"geslacht": geslacht})

    def upsert_koe(self, koe_data: Union[dict, Koe]) -> Koe:
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

    def mark_all_not_in_herd(self, animal_ids: List[UUID]) -> int:
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
