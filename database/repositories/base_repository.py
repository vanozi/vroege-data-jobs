# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
# ]
# ///

"""
Base repository with generic CRUD operations using SQLModel.

Follows the Repository pattern with DRY principles.
All model-specific repositories should inherit from this class.
"""

from typing import Generator, Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlmodel import Session, select
from contextlib import contextmanager

ModelType = TypeVar('ModelType')


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations using SQLModel.

    Provides common database operations that work with any SQLModel table.
    All model-specific repositories should inherit from this class.
    """

    def __init__(self, model: Type[ModelType], session_factory):
        """
        Initialize repository with model class and session factory.

        Args:
            model: SQLModel table class
            session_factory: Session factory from database configuration
        """
        self.model = model
        self.session_factory = session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager for database sessions with automatic commit/rollback"""
        session = self.session_factory() if callable(self.session_factory) else self.session_factory
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Create a new record.

        Args:
            data: Dictionary with model data

        Returns:
            Created model instance
        """
        with self.get_session() as session:
            instance = self.model(**data)
            session.add(instance)
            session.flush()
            session.refresh(instance)
            return instance

    def get_by_id(self, id_value: Any, id_field: str = None) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id_value: ID value to search for
            id_field: Name of ID field (defaults to primary key)

        Returns:
            Model instance or None
        """
        with self.get_session() as session:
            if id_field:
                # Use select() for custom field
                statement = select(self.model).where(
                    getattr(self.model, id_field) == id_value
                )
                return session.exec(statement).first()
            else:
                # Use session.get() for primary key
                return session.get(self.model, id_value)

    def get_all(self, filters: Dict[str, Any] = None, limit: int = None) -> List[ModelType]:
        """
        Get all records, optionally filtered.

        Args:
            filters: Dictionary of field:value pairs to filter by
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        with self.get_session() as session:
            statement = select(self.model)

            if filters:
                for field, value in filters.items():
                    statement = statement.where(getattr(self.model, field) == value)

            if limit:
                statement = statement.limit(limit)

            return session.exec(statement).all()

    def update(self, id_value: Any, data: Dict[str, Any], id_field: str = None) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id_value: ID value to search for
            data: Dictionary with fields to update
            id_field: Name of ID field (defaults to primary key)

        Returns:
            Updated model instance or None
        """
        with self.get_session() as session:
            if id_field:
                # Use select() for custom field
                statement = select(self.model).where(
                    getattr(self.model, id_field) == id_value
                )
                instance = session.exec(statement).first()
            else:
                # Use session.get() for primary key
                instance = session.get(self.model, id_value)

            if instance:
                for key, value in data.items():
                    setattr(instance, key, value)
                session.add(instance)
                session.flush()
                session.refresh(instance)

            return instance

    def delete(self, id_value: Any, id_field: str = None) -> bool:
        """
        Delete a record by ID.

        Args:
            id_value: ID value to search for
            id_field: Name of ID field (defaults to primary key)

        Returns:
            True if deleted, False if not found
        """
        with self.get_session() as session:
            if id_field:
                # Use select() for custom field
                statement = select(self.model).where(
                    getattr(self.model, id_field) == id_value
                )
                instance = session.exec(statement).first()
            else:
                # Use session.get() for primary key
                instance = session.get(self.model, id_value)

            if instance:
                session.delete(instance)
                return True
            return False

    def upsert(self, data: Dict[str, Any], unique_fields: List[str]) -> ModelType:
        """
        Insert or update a record based on unique fields.

        Args:
            data: Dictionary with model data
            unique_fields: List of field names to check for existing record

        Returns:
            Created or updated model instance
        """
        with self.get_session() as session:
            normalized_data = self._normalize_model_data(data)
            filters = self._build_unique_filters(normalized_data, unique_fields)
            instance = self._find_by_filters(session, filters)

            if instance:
                self._update_instance(instance, normalized_data)
            else:
                instance = self.model(**normalized_data)
                session.add(instance)

            session.flush()
            session.refresh(instance)
            return instance

    def _normalize_model_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input data through the model and remove None values.

        This gives callers consistent database-shaped values while avoiding
        explicit NULLs for fields that should use database defaults.
        """
        return self.model.model_validate(data).model_dump(exclude_none=True)

    def _build_unique_filters(
        self,
        data: Dict[str, Any],
        unique_fields: List[str],
    ) -> Dict[str, Any]:
        """Return the unique lookup values required for an upsert."""
        missing_fields = [
            field
            for field in unique_fields
            if field not in data or data[field] is None
        ]

        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"Missing unique field values for upsert: {missing}")

        return {field: data[field] for field in unique_fields}

    def _find_by_filters(
        self,
        session: Session,
        filters: Dict[str, Any],
    ) -> Optional[ModelType]:
        """Find the first model instance matching all filters."""
        statement = select(self.model)
        for field, value in filters.items():
            statement = statement.where(getattr(self.model, field) == value)

        return session.exec(statement).first()

    def _update_instance(
        self,
        instance: ModelType,
        data: Dict[str, Any],
    ) -> None:
        """Copy normalized data onto an existing model instance."""
        for key, value in data.items():
            setattr(instance, key, value)
