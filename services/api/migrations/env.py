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


def _run(conn) -> None:
    sqlite = conn.dialect.name == "sqlite"
    if sqlite:
        # SQLite changes a table by rebuilding it, which would break existing rows'
        # foreign keys mid-migration. Alembic's documented approach: switch the check
        # off for the migration, then verify every key afterwards. PostgreSQL
        # (AlloyDB) alters tables in place and needs none of this.
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.commit()
    context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=sqlite)
    with context.begin_transaction():
        context.run_migrations()
    if sqlite:
        broken = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()
        if broken:
            raise RuntimeError(f"migration left broken foreign keys: {broken[:5]}")


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine(_url())
    with engine.connect() as conn:
        _run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
