"""
Model registry for database metadata discovery.

Import table models here so tools like Alembic can load the full
SQLModel metadata from a single module import.
"""

from .behandeling import KlauwBehandeling
from .auth import Application, Role, User, UserApplicationAccess, UserApplicationRole
from .koe import Koe, KoeDetail
from .laying_hens import (
    DeadHenRegistration,
    EggPackagingWeightConfig,
    EggPalletWeightRegistration,
    EggRegistration,
    FeedWaterRegistration,
    Flock,
    FlockLayCurveNorm,
    FlockLayCurveProfile,
    OutsideNestEggRound,
)
from .melking import Melking
from .tank_transaction import TankTransaction

__all__ = [
    "Application",
    "DeadHenRegistration",
    "EggPackagingWeightConfig",
    "EggPalletWeightRegistration",
    "EggRegistration",
    "FeedWaterRegistration",
    "Flock",
    "FlockLayCurveNorm",
    "FlockLayCurveProfile",
    "KlauwBehandeling",
    "Koe",
    "KoeDetail",
    "Melking",
    "OutsideNestEggRound",
    "Role",
    "TankTransaction",
    "User",
    "UserApplicationAccess",
    "UserApplicationRole",
]
