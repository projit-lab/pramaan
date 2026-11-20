"""Add enrolment_challenges table.

Revision ID: 0004_enrolment_challenges
Revises: 0003_entry_route
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_enrolment_challenges"
down_revision = "0003_entry_route"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "enrolment_challenges",
        sa.Column("challenge_id", sa.String(40), nullable=False),
        sa.Column("approver_email", sa.String(254), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("challenge_id", name="pk_enrolment_challenges"),
        sa.UniqueConstraint("nonce", name="uq_enrolment_challenges_nonce"),
    )
    op.create_index(
        "ix_enrolment_challenges_approver_email",
        "enrolment_challenges",
        ["approver_email"],
    )


def downgrade() -> None:
    op.drop_table("enrolment_challenges")
