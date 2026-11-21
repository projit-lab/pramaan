"""Store the line hashes a batch summary binds, and when it was signed.

Revision ID: 0005_batch_signing
Revises: 0004_enrolment_challenges
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_batch_signing"
down_revision = "0004_enrolment_challenges"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("batches") as b:
        b.add_column(sa.Column("line_hashes", JSON, nullable=True))
        b.add_column(sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("batches") as b:
        b.drop_column("signed_at")
        b.drop_column("line_hashes")
