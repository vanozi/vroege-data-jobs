# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Base SQLModel classes and mixins.

SQLModel combines SQLAlchemy and Pydantic, providing:
- Database models with ORM capabilities
- Automatic Pydantic validation
- Unified model definition for DB and API
"""

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class TimestampMixin(SQLModel):
    """
    Mixin to add timestamp fields to models.

    Adds laatst_bijgewerkt (last updated) field that auto-updates on changes.
    """

    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class CreatedTimestampMixin(SQLModel):
    """
    Mixin to add created and updated timestamp fields.

    Adds both aangemaakt_op (created at) and laatst_bijgewerkt (last updated).
    """

    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
