from datetime import date
from typing import Union

from database.models.behandeling import KlauwBehandeling
from database.repositories.base_repository import BaseRepository
from sqlmodel import select


class KlauwBehandelingenRepository(BaseRepository[KlauwBehandeling]):
    """Repository for KlauwBehandeling model with specific operations"""

    def __init__(self, session_factory):
        super().__init__(KlauwBehandeling, session_factory)

    def upsert_klauw_behandeling(
        self,
        klauw_behandeling_data: Union[dict[str, object], KlauwBehandeling],
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
            unique_fields=["eartag_short", "behandeldatum", "notatie"],
        )

    def get_existing_behandeldatums(self) -> set[date]:
        """Return all treatment dates already stored for Klauwscore imports."""
        with self.get_session() as session:
            statement = select(self.model.behandeldatum).distinct()
            return set(session.exec(statement).all())

    def get_existing_pdf_hrefs(self) -> set[str]:
        """Return Klauwscore source PDF links already stored for imports."""
        with self.get_session() as session:
            statement = (
                select(self.model.pdf_href)
                .where(self.model.pdf_href.is_not(None))
                .distinct()
            )
            return set(session.exec(statement).all())
