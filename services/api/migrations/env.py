from __future__ import annotations

from alembic import context

from app.config import get_settings
from app.db.engine import database_url, make_engine
from app.db.models import Base

target_metadata = Base.metadata


def _url() -> str:
    # A caller (such as a test) may pass a URL in the config; otherwise use the app's.
    return context.config.get_main_option("sqlalchemy.url") or database_url(get_settings())


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(_url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
