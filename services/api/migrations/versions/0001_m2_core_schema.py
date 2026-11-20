"""M2 core schema: companies, approvers, devices, vendors with bank-account history,
payment intents, approvals, mandates, versioned policies.

Revision ID: 0001_m2_core_schema
Revises:
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_m2_core_schema"
down_revision = None
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("payer_account", sa.String(34), nullable=False),
        sa.Column("payer_ifsc", sa.String(11), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("company_id", name="pk_companies"),
    )
    op.create_table(
        "approvers",
        sa.Column("approver_id", sa.String(40), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_approvers_company_id_companies"
        ),
        sa.PrimaryKeyConstraint("approver_id", name="pk_approvers"),
        sa.UniqueConstraint("email", name="uq_approvers_email"),
    )
    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(40), nullable=False),
        sa.Column("approver_email", sa.String(254), nullable=False),
        sa.Column("phone_model", sa.String(100), nullable=True),
        sa.Column("public_key_pem", sa.Text(), nullable=True),
        sa.Column("key_security_level", sa.String(30), nullable=True),
        sa.Column("patch_level", sa.String(20), nullable=True),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("enrolled_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["approver_email"], ["approvers.email"], name="fk_devices_approver_email_approvers"
        ),
        sa.PrimaryKeyConstraint("device_id", name="pk_devices"),
    )
    op.create_index("ix_devices_approver_email", "devices", ["approver_email"])
    op.create_table(
        "vendors",
        sa.Column("vendor_id", sa.String(40), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("onboarded_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_vendors_company_id_companies"
        ),
        sa.PrimaryKeyConstraint("vendor_id", name="pk_vendors"),
    )
    op.create_index("ix_vendors_company_id", "vendors", ["company_id"])
    op.create_table(
        "vendor_bank_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vendor_id", sa.String(40), nullable=False),
        sa.Column("account_number", sa.String(34), nullable=False),
        sa.Column("ifsc", sa.String(11), nullable=False),
        sa.Column("name_at_bank", sa.String(200), nullable=False),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_to", TS, nullable=True),
        sa.Column("changed_by", sa.String(254), nullable=True),
        sa.Column("verification", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.vendor_id"], name="fk_vendor_bank_accounts_vendor_id_vendors"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_bank_accounts"),
    )
    op.create_index(
        "ix_vendor_bank_accounts_vendor_current", "vendor_bank_accounts", ["vendor_id", "valid_to"]
    )
    op.create_table(
        "payment_intents",
        sa.Column("intent_id", sa.String(40), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("vendor_id", sa.String(40), nullable=True),
        sa.Column("payee_name", sa.String(200), nullable=False),
        sa.Column("payee_account", sa.String(34), nullable=True),
        sa.Column("payee_account_last4", sa.String(4), nullable=False),
        sa.Column("payee_ifsc", sa.String(11), nullable=False),
        sa.Column("payer_account", sa.String(34), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=True),
        sa.Column("invoice_sha256", sa.String(64), nullable=True),
        sa.Column("instruction_channel", sa.String(10), nullable=False),
        sa.Column("instruction_note", sa.Text(), nullable=True),
        sa.Column("initiator_type", sa.String(10), nullable=False),
        sa.Column("initiator_id", sa.String(254), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("reasons", JsonType, nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("approvers", JsonType, nullable=False),
        sa.Column("decided_by", sa.String(254), nullable=True),
        sa.Column("mandate_id", sa.String(40), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="ck_payment_intents_amount_positive"),
        sa.CheckConstraint("tier BETWEEN 0 AND 3", name="ck_payment_intents_tier_range"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_payment_intents_company_id_companies"
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.vendor_id"], name="fk_payment_intents_vendor_id_vendors"
        ),
        sa.PrimaryKeyConstraint("intent_id", name="pk_payment_intents"),
    )
    op.create_index(
        "ix_payment_intents_status_created", "payment_intents", ["status", "created_at"]
    )
    op.create_index("ix_payment_intents_payee_account", "payment_intents", ["payee_account"])
    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(40), nullable=False),
        sa.Column("intent_id", sa.String(40), nullable=False),
        sa.Column("approver_email", sa.String(254), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("canonical_summary", sa.Text(), nullable=True),
        sa.Column("summary_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("decision", sa.String(15), nullable=True),
        sa.Column("decided_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["payment_intents.intent_id"],
            name="fk_approvals_intent_id_payment_intents",
        ),
        sa.PrimaryKeyConstraint("approval_id", name="pk_approvals"),
        sa.UniqueConstraint("intent_id", "approver_email", name="uq_approvals_intent_approver"),
        sa.UniqueConstraint("nonce", name="uq_approvals_nonce"),
    )
    op.create_index("ix_approvals_intent_id", "approvals", ["intent_id"])
    op.create_index("ix_approvals_approver_status", "approvals", ["approver_email", "status"])
    op.create_table(
        "mandates",
        sa.Column("mandate_id", sa.String(40), nullable=False),
        sa.Column("intent_id", sa.String(40), nullable=False),
        sa.Column("document", JsonType, nullable=False),
        sa.Column("summary_sha256", sa.String(64), nullable=False),
        sa.Column("kms_key_version", sa.String(300), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("used_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["payment_intents.intent_id"],
            name="fk_mandates_intent_id_payment_intents",
        ),
        sa.PrimaryKeyConstraint("mandate_id", name="pk_mandates"),
    )
    op.create_index("ix_mandates_intent_id", "mandates", ["intent_id"])
    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("document", JsonType, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("published_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_policies_company_id_companies"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policies"),
        sa.UniqueConstraint("company_id", "version", name="uq_policies_company_version"),
    )


def downgrade() -> None:
    for table in (
        "policies",
        "mandates",
        "approvals",
        "payment_intents",
        "vendor_bank_accounts",
        "vendors",
        "devices",
        "approvers",
        "companies",
    ):
        op.drop_table(table)
