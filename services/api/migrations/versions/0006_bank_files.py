"""Bank payment files: one uploaded file, one intent per line.

A bank file is the second of the four doors. Finance uploads a payment file the
way they would hand one to their bank, and every line becomes an ordinary
payment intent that goes through exactly the same gate. The file itself is kept
so the clerk can be told, honestly, that it is not finished until every risky
line in it has been decided.

bank_file_lines holds the line number against the intent it became, so the
file's progress can be read back without storing a second copy of the payment.

Revision ID: 0006_bank_files
Revises: 0005_batch_signing
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_bank_files"
down_revision = "0005_batch_signing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_files",
        sa.Column("file_id", sa.String(40), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(40),
            sa.ForeignKey("companies.company_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(260), nullable=False),
        # So the same file uploaded twice is recognisable, and so the clerk can
        # be shown that the file Pramaan read is the file they sent.
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.String(254), nullable=False),
        sa.Column("line_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "bank_file_lines",
        sa.Column("file_id", sa.String(40), sa.ForeignKey("bank_files.file_id"), primary_key=True),
        sa.Column("line_no", sa.Integer, primary_key=True),
        sa.Column(
            "intent_id",
            sa.String(40),
            sa.ForeignKey("payment_intents.intent_id"),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("bank_file_lines")
    op.drop_table("bank_files")
