# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Repository for Koe (Cow) model with specific operations using SQLModel.
"""

from typing import Union
from .base_repository import BaseRepository
from database.models import Melking


class MelkingenRepository(BaseRepository[Melking]):
    """Repository for Melking model with specific operations"""

    def __init__(self, session_factory):
        super().__init__(Melking, session_factory)

    def upsert_melking(self, melking_data: Union[dict, Melking]) -> Melking:
        """
        Insert or update koe data.

        Args:
            melking_data: Dictionary with melking data OR Melking SQLModel object

        Returns:
            Melink instance
        """
        # Convert Koe object to dict if needed
        if isinstance(melking_data, Melking):
            melking_data = melking_data.model_dump()

        return self.upsert(melking_data, unique_fields=["id"])
