from typing import Union
from .base_repository import BaseRepository
from database.models import KoeDetail


class KoeDetailRepository(BaseRepository[KoeDetail]):
    """Repository for KoeDetail model with specific operations"""

    def __init__(self, session_factory):
        super().__init__(KoeDetail, session_factory)

    def upsert_koe_detail(self, koe_detail_data: Union[dict, KoeDetail]) -> KoeDetail:
        """
        Insert or update koe detail data.

        Args:
            koe_detail_data: Dictionary with koe detail data OR KoeDetail SQLModel object
        Returns:
            KoeDetail instance
        """
        # Convert Koe object to dict if needed
        if isinstance(koe_detail_data, KoeDetail):
            koe_detail_data = koe_detail_data.model_dump()

        return self.upsert(koe_detail_data, unique_fields=["animal_id"])
