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
    """Create or return the global SQLAlchemy engine with connection pooling."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url_obj = settings.get_database_url_object()

        if isinstance(db_url_obj, str) and db_url_obj.startswith("sqlite"):
            _engine = create_engine(
                db_url_obj,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            # PyMySQL / Remote MySQL Pool using safely constructed URL object
            _engine = create_engine(
                db_url_obj,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=settings.db_pool_recycle,
                pool_timeout=settings.db_pool_timeout,
                pool_pre_ping=True,  # Automatically reconnect dropped MySQL connections
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
