"""Add entry_route to payment intents: erp, bank_file, payout_api or agent.

Existing rows were all created through the ERP connector or the agent, so they
are back-filled from the initiator before the column becomes required.

Revision ID: 0003_entry_route
Revises: 0002_m2plus_hierarchy
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_entry_route"
down_revision = "0002_m2plus_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payment_intents") as b:
        b.add_column(sa.Column("entry_route", sa.String(12), nullable=True))
    op.execute(
        "UPDATE payment_intents SET entry_route = "
        "CASE WHEN initiator_type = 'agent' THEN 'agent' ELSE 'erp' END"
    )
    with op.batch_alter_table("payment_intents") as b:
        b.alter_column("entry_route", existing_type=sa.String(12), nullable=False)
        b.create_check_constraint(
            "ck_payment_intents_entry_route_known",
            "entry_route IN ('erp', 'bank_file', 'payout_api', 'agent')",
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_intents") as b:
        b.drop_constraint("ck_payment_intents_entry_route_known", type_="check")
        b.drop_column("entry_route")
