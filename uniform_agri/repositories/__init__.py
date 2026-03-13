# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Repository layer for database operations using SQLModel.

All repositories follow the Repository pattern with generic CRUD operations
from BaseRepository and model-specific methods.
"""

from .base_repository import BaseRepository
from .koe_repository import KoeRepository

__all__ = [
    'BaseRepository',
    'KoeRepository',
]
