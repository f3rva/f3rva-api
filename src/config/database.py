"""SQLAlchemy 2.0 Database Engine & Session Pool Management."""

from __future__ import annotations

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


# Cached engine and sessionmaker singletons for Lambda connection reuse
_engine = None
_SessionLocal = None


def get_engine():
    """Create or return the global SQLAlchemy engine from the externalized DATABASE_URL with zero dialect checks."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_recycle=settings.db_pool_recycle,
            connect_args=settings.db_connect_args,
        )
    return _engine


def get_sessionmaker():
    """Create or return the global session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    session_factory = get_sessionmaker()
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()
