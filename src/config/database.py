"""SQLAlchemy 2.0 Database Engine & Session Pool Management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""

    pass


# Cached engine and sessionmaker singletons for Lambda connection reuse
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create or return the global SQLAlchemy engine from the externalized DATABASE_URL with zero dialect checks."""
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url = settings.database_url or "sqlite:///:memory:"
        kwargs: dict[str, Any] = {}
        if settings.db_pool_pre_ping is not None:
            kwargs["pool_pre_ping"] = settings.db_pool_pre_ping
        if settings.db_pool_recycle is not None:
            kwargs["pool_recycle"] = settings.db_pool_recycle
        if settings.db_connect_args is not None:
            kwargs["connect_args"] = settings.db_connect_args
        _engine = create_engine(database_url, **kwargs)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Create or return the global session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a database session per request."""
    session_factory = get_sessionmaker()
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()
