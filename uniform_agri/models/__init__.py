# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Database models for the application using SQLModel.

SQLModel combines SQLAlchemy and Pydantic:
- Type-safe database models
- Automatic validation
- Can be used directly as API response models

All models can be imported from this module.
"""

from .base import TimestampMixin, CreatedTimestampMixin
from .koe import Koe, KoeDetail
from .melking import Melking

__all__ = [
    'TimestampMixin',
    'CreatedTimestampMixin',
    'Koe',
    'KoeDetail',
    'Melking',
]
