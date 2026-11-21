"""Hold the verified phone signature while a Tier 2 approval waits for the spoken code.

Revision ID: 0007_voice_pending
Revises: 0006_bank_files
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_voice_pending"
down_revision = "0006_bank_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("approvals") as b:
        b.add_column(sa.Column("pending_signature_b64", sa.Text(), nullable=True))
        b.add_column(sa.Column("pending_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("approvals") as b:
        b.drop_column("pending_summary")
        b.drop_column("pending_signature_b64")
