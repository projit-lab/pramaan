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
    # M2+
    "org_nodes",
    "org_rules",
    "delegations",
    "standing_mandates",
    "standing_mandate_usage",
    "batches",
    "enrolment_challenges",
    # The file door
    "bank_files",
    "bank_file_lines",
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


def test_upgrade_from_m2_keeps_existing_payments(tmp_path):
    """A database that already holds M2 payments and approvals upgrades to M2+ with
    every row and every foreign key intact (this failed before the SQLite fix)."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text

    from app.db.engine import make_session_factory, unit_of_work
    from app.db.seed import seed_m2plus_if_missing

    url = f"sqlite:///{(tmp_path / 'upgrade.db').as_posix()}"
    cfg = _alembic(url)
    command.upgrade(cfg, "0001_m2_core_schema")
    engine = make_engine(url)
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO companies VALUES ('co_acme','Acme','50100004521','HDFC0000452',:t)"),
            {"t": now},
        )
        conn.execute(
            text(
                "INSERT INTO approvers VALUES"
                " ('apr_cfo','co_acme','cfo@acme.example','Priya','CFO',1,:t)"
            ),
            {"t": now},
        )
        conn.execute(
            text(
                "INSERT INTO payment_intents (intent_id, company_id, payee_name,"
                " payee_account_last4, payee_ifsc, payer_account, amount_paise, currency,"
                " instruction_channel,"
                " initiator_type, initiator_id, decision, status, tier, reasons, policy_version,"
                " approvers, created_at, updated_at) VALUES ('pi_OLD','co_acme','X','1234',"
                "'ABCD0123456','50100004521',100,'INR','portal','human','c','hold','held',1,'[]',"
                "'2026.11.1','[\"cfo@acme.example\"]',:t,:t)"
            ),
            {"t": now},
        )
        conn.execute(
            text(
                "INSERT INTO approvals (approval_id, intent_id, approver_email, nonce, status,"
                " created_at, expires_at) VALUES ('ap_OLD','pi_OLD','cfo@acme.example','n1',"
                "'pending',:t,:e)"
            ),
            {"t": now, "e": now + timedelta(hours=24)},
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM approvals")).scalar() == 1
        assert conn.execute(text("SELECT lane FROM payment_intents")).scalar() is None
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    seed_m2plus_if_missing(make_session_factory(engine))
    with unit_of_work(make_session_factory(engine)) as s:
        assert (
            s.execute(text("SELECT level FROM approvers WHERE email='cfo@acme.example'")).scalar()
            == 3
        )
    engine.dispose()


def test_every_m2_table_is_modelled():
    assert TABLES == set(Base.metadata.tables)


@pytest.mark.parametrize("table", ["payment_intents", "approvals"])
def test_money_and_ids_are_not_floats(table):
    cols = Base.metadata.tables[table].columns
    if "amount_paise" in cols:
        assert cols["amount_paise"].type.python_type is int
