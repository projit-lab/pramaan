"""Database engine and sessions.

Cloud: DATABASE_URL points at AlloyDB (PostgreSQL). Local: a SQLite file under the
gitignored .local/ directory, so `uvicorn app.main:app` works with no database
server. Tests pass their own URL.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

LOCAL_DIR = Path(__file__).resolve().parents[2] / ".local"


def database_url(settings: Settings) -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    if settings.ENV != "local":
        raise RuntimeError("DATABASE_URL must be set outside ENV=local (AlloyDB connection string)")
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(LOCAL_DIR / 'pramaan.db').as_posix()}"


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_conn, _record):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def unit_of_work(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One transaction: commit on success, roll back on any error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
