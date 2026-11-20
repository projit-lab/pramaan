"""M2+: organisation tree with CEL rules, approver levels, delegations, standing
mandates with usage counters, batches, and the lane / trace / payee-check fields
on payment intents and approvals.

Revision ID: 0002_m2plus_hierarchy
Revises: 0001_m2_core_schema
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_m2plus_hierarchy"
down_revision = "0001_m2_core_schema"
branch_labels = None
depends_on = None

JsonType = sa.JSON().with_variant(JSONB(), "postgresql")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "org_nodes",
        sa.Column("node_id", sa.String(40), nullable=False),
        sa.Column("parent_id", sa.String(40), nullable=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=True),
        sa.Column("settings", JsonType, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["org_nodes.node_id"], name="fk_org_nodes_parent_id_org_nodes"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_org_nodes_company_id_companies"
        ),
        sa.PrimaryKeyConstraint("node_id", name="pk_org_nodes"),
    )
    op.create_index("ix_org_nodes_parent_id", "org_nodes", ["parent_id"])
    op.create_table(
        "org_rules",
        sa.Column("rule_id", sa.String(40), nullable=False),
        sa.Column("node_id", sa.String(40), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("min_tier", sa.Integer(), nullable=False),
        sa.Column("hard_flag", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["node_id"], ["org_nodes.node_id"], name="fk_org_rules_node_id_org_nodes"
        ),
        sa.PrimaryKeyConstraint("rule_id", name="pk_org_rules"),
        sa.UniqueConstraint("node_id", "code", name="uq_org_rules_node_code"),
    )
    op.create_index("ix_org_rules_node_id", "org_rules", ["node_id"])
    op.create_table(
        "delegations",
        sa.Column("delegation_id", sa.String(40), nullable=False),
        sa.Column("delegator_email", sa.String(254), nullable=False),
        sa.Column("delegate_email", sa.String(254), nullable=False),
        sa.Column("valid_from", TS, nullable=False),
        sa.Column("valid_to", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["delegator_email"],
            ["approvers.email"],
            name="fk_delegations_delegator_email_approvers",
        ),
        sa.ForeignKeyConstraint(
            ["delegate_email"], ["approvers.email"], name="fk_delegations_delegate_email_approvers"
        ),
        sa.PrimaryKeyConstraint("delegation_id", name="pk_delegations"),
    )
    op.create_index("ix_delegations_delegator_email", "delegations", ["delegator_email"])
    op.create_table(
        "standing_mandates",
        sa.Column("standing_mandate_id", sa.String(40), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("vendor_id", sa.String(40), nullable=False),
        sa.Column("payee_account_sha256", sa.String(64), nullable=False),
        sa.Column("payee_ifsc", sa.String(11), nullable=False),
        sa.Column("cap_per_payment_paise", sa.BigInteger(), nullable=False),
        sa.Column("cap_per_month_paise", sa.BigInteger(), nullable=False),
        sa.Column("max_count", sa.Integer(), nullable=False),
        sa.Column("approver_email", sa.String(254), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.company_id"],
            name="fk_standing_mandates_company_id_companies",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"], ["vendors.vendor_id"], name="fk_standing_mandates_vendor_id_vendors"
        ),
        sa.PrimaryKeyConstraint("standing_mandate_id", name="pk_standing_mandates"),
    )
    op.create_index("ix_standing_mandates_vendor_id", "standing_mandates", ["vendor_id"])
    op.create_table(
        "standing_mandate_usage",
        sa.Column("standing_mandate_id", sa.String(40), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("total_paise", sa.BigInteger(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("total_paise >= 0", name="ck_standing_mandate_usage_total_non_negative"),
        sa.CheckConstraint("used_count >= 0", name="ck_standing_mandate_usage_count_non_negative"),
        sa.ForeignKeyConstraint(
            ["standing_mandate_id"],
            ["standing_mandates.standing_mandate_id"],
            name="fk_standing_mandate_usage_standing_mandate_id_standing_mandates",
        ),
        sa.PrimaryKeyConstraint("standing_mandate_id", "month", name="pk_standing_mandate_usage"),
    )
    op.create_table(
        "batches",
        sa.Column("batch_id", sa.String(40), nullable=False),
        sa.Column("company_id", sa.String(40), nullable=False),
        sa.Column("department_id", sa.String(40), nullable=True),
        sa.Column("window_at", TS, nullable=False),
        sa.Column("approver_email", sa.String(254), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("total_paise", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.company_id"], name="fk_batches_company_id_companies"
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["org_nodes.node_id"], name="fk_batches_department_id_org_nodes"
        ),
        sa.PrimaryKeyConstraint("batch_id", name="pk_batches"),
        sa.UniqueConstraint("nonce", name="uq_batches_nonce"),
    )
    op.create_index("ix_batches_window_at", "batches", ["window_at"])

    with op.batch_alter_table("approvers") as b:
        b.add_column(sa.Column("level", sa.Integer(), nullable=True))
        b.add_column(sa.Column("node_id", sa.String(40), nullable=True))
        b.create_foreign_key(
            "fk_approvers_node_id_org_nodes", "org_nodes", ["node_id"], ["node_id"]
        )

    with op.batch_alter_table("payment_intents") as b:
        b.add_column(sa.Column("department_id", sa.String(40), nullable=True))
        b.add_column(sa.Column("lane", sa.String(15), nullable=True))
        b.add_column(sa.Column("decision_trace", JsonType, nullable=True))
        b.add_column(sa.Column("payee_checks", JsonType, nullable=True))
        b.add_column(sa.Column("batch_window_at", TS, nullable=True))
        b.add_column(sa.Column("batch_id", sa.String(40), nullable=True))
        b.add_column(sa.Column("standing_mandate_id", sa.String(40), nullable=True))
        b.create_foreign_key(
            "fk_payment_intents_department_id_org_nodes",
            "org_nodes",
            ["department_id"],
            ["node_id"],
        )

    with op.batch_alter_table("approvals") as b:
        b.add_column(sa.Column("required_level", sa.Integer(), nullable=True))
        b.add_column(sa.Column("escalate_at", TS, nullable=True))
        b.add_column(sa.Column("escalated_from", sa.String(40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("approvals") as b:
        b.drop_column("escalated_from")
        b.drop_column("escalate_at")
        b.drop_column("required_level")
    with op.batch_alter_table("payment_intents") as b:
        b.drop_constraint("fk_payment_intents_department_id_org_nodes", type_="foreignkey")
        for col in (
            "standing_mandate_id",
            "batch_id",
            "batch_window_at",
            "payee_checks",
            "decision_trace",
            "lane",
            "department_id",
        ):
            b.drop_column(col)
    with op.batch_alter_table("approvers") as b:
        b.drop_constraint("fk_approvers_node_id_org_nodes", type_="foreignkey")
        b.drop_column("node_id")
        b.drop_column("level")
    for table in (
        "batches",
        "standing_mandate_usage",
        "standing_mandates",
        "delegations",
        "org_rules",
        "org_nodes",
    ):
        op.drop_table(table)
