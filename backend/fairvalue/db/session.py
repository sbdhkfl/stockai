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

_engines: dict = {}


def get_engine(url: str | None = None):
    # Resolve the URL at call time: FAIRVALUE_DB_URL may be set after this
    # module is imported (tests, uvicorn --reload). Cache per URL so engine
    # pools are reused instead of leaked.
    url = url or os.environ.get("FAIRVALUE_DB_URL") or DEFAULT_URL
    if url not in _engines:
        kwargs: dict = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engines[url] = create_engine(url, **kwargs)
    return _engines[url]


def create_all(engine=None) -> None:
    """Convenience bootstrap for tests/dev. Production uses Alembic migrations
    (fairvalue/db/migrations) — do not rely on create_all there."""
    Base.metadata.create_all(engine or get_engine())


def make_session(engine=None) -> Session:
    engine = engine or get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)()
