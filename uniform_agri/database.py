# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "sqlmodel",
#     "python-dotenv",
# ]
# ///

"""
Centralized database configuration and session management.

This module provides:
- Single engine instance with proper configuration
- Session factory for dependency injection
- Database initialization and table creation
- Environment-based configuration
"""

import os
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/gebroeders-vroege")

# Create engine with appropriate settings based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific settings
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        connect_args=connect_args,
    )
elif DATABASE_URL.startswith("postgresql"):
    # PostgreSQL production settings with connection pooling
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_size=5,              # Number of connections to keep open
        max_overflow=10,          # Additional connections when pool is full
        pool_pre_ping=True,       # Verify connections before using (handles dropped connections)
        pool_recycle=3600,        # Recycle connections after 1 hour
    )
else:
    # Default settings for other databases (MySQL, etc.)
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def init_db() -> None:
    """
    Initialize database by creating all tables.

    Call this once at application startup.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Create a new database session.

    Returns:
        Session: SQLModel session instance

    Usage:
        session = get_session()
        try:
            # Use session
            pass
        finally:
            session.close()
    """
    return Session(engine)


@contextmanager
def get_session_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic commit/rollback.

    Yields:
        Session: SQLModel session instance

    Usage:
        with get_session_context() as session:
            # Use session
            session.add(obj)
            # Automatically commits on success, rolls back on error
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection function for FastAPI.

    Yields:
        Session: SQLModel session instance

    Usage in FastAPI:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items
    """
    with get_session_context() as session:
        yield session


# Convenience exports for common use cases
__all__ = [
    "engine",
    "init_db",
    "get_session",
    "get_session_context",
    "get_db",
    "DATABASE_URL",
]
