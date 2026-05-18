"""
Model registry for database metadata discovery.

Import table models here so tools like Alembic can load the full
SQLModel metadata from a single module import.
"""

from .behandeling import KlauwBehandeling
from .koe import Koe, KoeDetail
from .melking import Melking

__all__ = [
    "KlauwBehandeling",
    "Koe",
    "KoeDetail",
    "Melking",
]
