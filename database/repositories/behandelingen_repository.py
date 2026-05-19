from database.models.behandeling import KlauwBehandeling
from database.repositories.base_repository import BaseRepository


class KlauwBehandelingenRepository(BaseRepository[KlauwBehandeling]):
    """Repository for KlauwBehandeling model with specific operations"""

    def __init__(self, session_factory):
        super().__init__(KlauwBehandeling, session_factory)

    def upsert_klauw_behandeling(
        self,
        klauw_behandeling_data: dict[str, object] | KlauwBehandeling,
    ) -> KlauwBehandeling:
        """
        Insert or update klauw behandeling.

        Args:
            klauw_behandeling_data: Dictionary with klauw behandeling data OR
                KlauwBehandeling SQLModel object.
        Returns:
            KlauwBehandeling instance
        """
        if isinstance(klauw_behandeling_data, KlauwBehandeling):
            klauw_behandeling_data = klauw_behandeling_data.model_dump()

        return self.upsert(
            klauw_behandeling_data,
            unique_fields=["halsbandnummer", "behandeldatum", "notatie"],
        )
