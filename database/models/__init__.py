"""
Model registry for database metadata discovery.

Import table models here so tools like Alembic can load the full
SQLModel metadata from a single module import.
"""

from .behandeling import KlauwBehandeling
from .koe import Koe, KoeDetail
from .laying_hens import (
    DailyLayingRegistration,
    DeadHenRegistration,
    Flock,
    OutsideNestEggRound,
)
from .melking import Melking
from .tank_transaction import TankTransaction

__all__ = [
    "DailyLayingRegistration",
    "DeadHenRegistration",
    "Flock",
    "KlauwBehandeling",
    "Koe",
    "KoeDetail",
    "Melking",
    "OutsideNestEggRound",
    "TankTransaction",
]
