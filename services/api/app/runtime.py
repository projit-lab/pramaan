"""Process-wide dependencies for the M2 routers, built once and shared.

The skeleton's adapter factories return a fresh object per call; the database,
the event bus, the read model and the notifier must be shared across requests,
so they live here. Built lazily on the first request (or injected by tests).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.event_bus import get_event_bus
from app.adapters.notifier import Notifier, get_notifier
from app.adapters.read_model import get_read_model
from app.config import Settings, get_settings
from app.db.engine import database_url, make_engine, make_session_factory

logger = logging.getLogger("pramaan")
API_DIR = Path(__file__).resolve().parents[1]


@dataclass
class Runtime:
    settings: Settings
    sessions: sessionmaker[Session]
    event_bus: Any
    read_model: Any
    notifier: Notifier
    # Injected in tests so time-based rules (working hours, expiry) are repeatable.
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))


def migrate(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def build_runtime(settings: Settings, url: str | None = None, seed: bool | None = None) -> Runtime:
    url = url or database_url(settings)
    engine = make_engine(url)
    sessions = make_session_factory(engine)
    if settings.ENV == "local":
        # Local only: bring the schema up to date and load demo data. In the cloud,
        # `alembic upgrade head` runs as a deploy step, never at request time.
        migrate(url)
    if seed if seed is not None else (settings.ENV == "local" or settings.DEMO_MODE):
        from app.db.seed import seed_if_empty, seed_m2plus_if_missing

        seed_if_empty(sessions, settings.COMPANY_ID)
        seed_m2plus_if_missing(sessions, settings.COMPANY_ID)
    return Runtime(
        settings=settings,
        sessions=sessions,
        event_bus=get_event_bus(settings),
        read_model=get_read_model(settings),
        notifier=get_notifier(settings),
    )


def utc_now(rt: Runtime) -> datetime:
    """Now, in UTC. Everything is stored in UTC: SQLite drops the offset on write,
    so storing an IST time would read back 5.5 hours off."""
    return rt.clock().astimezone(timezone.utc)


def get_runtime(request: Request) -> Runtime:
    rt = getattr(request.app.state, "runtime", None)
    if rt is None:
        rt = build_runtime(get_settings())
        request.app.state.runtime = rt
    return rt
