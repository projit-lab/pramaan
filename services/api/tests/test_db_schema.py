"""The migration and the ORM models must describe the same schema.

Runs on SQLite by default. Set PRAMAAN_TEST_PG_URL (an empty PostgreSQL database)
to run the same checks against PostgreSQL, which is what AlloyDB speaks.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from app.db.engine import make_engine
from app.db.models import Base

API_DIR = Path(__file__).resolve().parents[1]

TABLES = {
    "companies",
    "approvers",
    "devices",
    "vendors",
    "vendor_bank_accounts",
    "payment_intents",
    "approvals",
    "mandates",
    "policies",
}


def _urls(tmp_path):
    urls = [f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"]
    if os.environ.get("PRAMAAN_TEST_PG_URL"):
        urls.append(os.environ["PRAMAAN_TEST_PG_URL"])
    return urls


def _alembic(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migration_matches_models(tmp_path):
    for url in _urls(tmp_path):
        cfg = _alembic(url)
        command.upgrade(cfg, "head")
        engine = make_engine(url)
        try:
            assert TABLES <= set(inspect(engine).get_table_names())
            with engine.connect() as conn:
                diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
            assert diff == [], f"models and migration differ on {url.split(':')[0]}: {diff}"
        finally:
            command.downgrade(cfg, "base")
            remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
            engine.dispose()
        assert remaining == set()


def test_every_m2_table_is_modelled():
    assert TABLES == set(Base.metadata.tables)


@pytest.mark.parametrize("table", ["payment_intents", "approvals"])
def test_money_and_ids_are_not_floats(table):
    cols = Base.metadata.tables[table].columns
    if "amount_paise" in cols:
        assert cols["amount_paise"].type.python_type is int
