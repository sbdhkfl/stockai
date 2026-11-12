"""Engine/session factory. Database URL from FAIRVALUE_DB_URL (default:
SQLite file). PostgreSQL-compatible: pass e.g.
FAIRVALUE_DB_URL=postgresql+psycopg://user:pass@host/fairvalue — no code
changes; Alembic migrations are dialect-agnostic.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from fairvalue.db.models import Base

DEFAULT_URL = os.environ.get("FAIRVALUE_DB_URL", "sqlite:///./fairvalue.db")

_engine = None


def get_engine(url: str | None = None):
    global _engine
    if url is None and _engine is not None:
        return _engine
    url = url or DEFAULT_URL
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url is None:
        _engine = engine
    return engine


def create_all(engine=None) -> None:
    """Convenience bootstrap for tests/dev. Production uses Alembic migrations
    (fairvalue/db/migrations) — do not rely on create_all there."""
    Base.metadata.create_all(engine or get_engine())


def make_session(engine=None) -> Session:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)()
