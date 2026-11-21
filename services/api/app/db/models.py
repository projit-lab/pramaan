"""System of record (AlloyDB for PostgreSQL). M2, Danish.

Tables: companies, approvers, devices, vendors, vendor_bank_accounts (full
history), payment_intents, approvals, mandates, policies (versioned).

Conventions:
- Money is an integer number of paise in BIGINT; the API sends it as a string.
- Full account numbers live only here. Events, logs and the read model carry the
  last four digits.
- Timestamps are timezone-aware and stored in UTC; the API renders them in IST.
- The schema is written once in migrations/versions/0001_m2_core_schema.py; a test
  checks these models and that migration never drift apart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    payer_account: Mapped[str] = mapped_column(String(34))
    payer_ifsc: Mapped[str] = mapped_column(String(11))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Approver(Base):
    __tablename__ = "approvers"

    approver_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    # AP Manager, Controller, CFO, MD.
    role: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # M2+: seniority (1 AP Manager, 2 Controller, 3 CFO, 4 MD) and where in the
    # organisation tree this approver sits. Routing walks up from the department.
    level: Mapped[int | None] = mapped_column(Integer)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("org_nodes.node_id"))


class Device(Base):
    """Approver phones. Prajit's M1 enrolment fills the key fields; routing reads
    fcm_token to send the 'approval waiting' data message."""

    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    approver_email: Mapped[str] = mapped_column(ForeignKey("approvers.email"), index=True)
    phone_model: Mapped[str | None] = mapped_column(String(100))
    public_key_pem: Mapped[str | None] = mapped_column(Text)
    key_security_level: Mapped[str | None] = mapped_column(String(30))
    patch_level: Mapped[str | None] = mapped_column(String(20))
    fcm_token: Mapped[str | None] = mapped_column(Text)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnrolmentChallenge(Base):
    """One-time random nonce issued to an approver for Android Key Attestation enrolment."""

    __tablename__ = "enrolment_challenges"

    challenge_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    approver_email: Mapped[str] = mapped_column(String(254), index=True)
    nonce: Mapped[str] = mapped_column(String(64), unique=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"), index=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    # When the vendor relationship began; months of history are counted from here.
    onboarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class VendorBankAccount(Base):
    """Full bank-account history. The current account has valid_to NULL; a bank
    change closes the old row and opens a new one, so nothing is overwritten."""

    __tablename__ = "vendor_bank_accounts"
    __table_args__ = (Index("ix_vendor_bank_accounts_vendor_current", "vendor_id", "valid_to"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"))
    account_number: Mapped[str] = mapped_column(String(34))
    ifsc: Mapped[str] = mapped_column(String(11))
    name_at_bank: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Who recorded the change, and how it was verified (name check, call-back).
    changed_by: Mapped[str | None] = mapped_column(String(254))
    verification: Mapped[str | None] = mapped_column(String(200))


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="amount_positive"),
        CheckConstraint("tier BETWEEN 0 AND 3", name="tier_range"),
        CheckConstraint(
            "entry_route IN ('erp', 'bank_file', 'payout_api', 'agent')", name="entry_route_known"
        ),
        Index("ix_payment_intents_status_created", "status", "created_at"),
        Index("ix_payment_intents_payee_account", "payee_account"),
    )

    intent_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.vendor_id"))
    payee_name: Mapped[str] = mapped_column(String(200))
    # Full number only when the payee came from the vendor master; a one-off payee
    # arrives with the last four digits only (see IntentCreate in the contract).
    payee_account: Mapped[str | None] = mapped_column(String(34))
    payee_account_last4: Mapped[str] = mapped_column(String(4))
    payee_ifsc: Mapped[str] = mapped_column(String(11))
    payer_account: Mapped[str] = mapped_column(String(34))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    purpose: Mapped[str | None] = mapped_column(String(200))
    invoice_sha256: Mapped[str | None] = mapped_column(String(64))
    instruction_channel: Mapped[str] = mapped_column(String(10))
    # The system the payment came in through: erp, bank_file, payout_api, agent.
    entry_route: Mapped[str] = mapped_column(String(12))
    instruction_note: Mapped[str | None] = mapped_column(Text)
    initiator_type: Mapped[str] = mapped_column(String(10))
    initiator_id: Mapped[str] = mapped_column(String(254))
    decision: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))
    tier: Mapped[int] = mapped_column(Integer)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JsonType)
    policy_version: Mapped[str] = mapped_column(String(40))
    approvers: Mapped[list[str]] = mapped_column(JsonType)
    decided_by: Mapped[str | None] = mapped_column(String(254))
    mandate_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # M2+: where the payment sits in the tree, which lane it went to, every rule
    # that fired with its path, and the automatic payee checks.
    department_id: Mapped[str | None] = mapped_column(ForeignKey("org_nodes.node_id"))
    lane: Mapped[str | None] = mapped_column(String(15))  # individual, batch, auto_release
    decision_trace: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    payee_checks: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    batch_window_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_id: Mapped[str | None] = mapped_column(String(40))
    standing_mandate_id: Mapped[str | None] = mapped_column(String(40))


class Approval(Base):
    """One per approver per held intent. nonce, canonical_summary and
    summary_sha256 are Prajit's: routing issues the nonce, and his M1 code fills
    the summary the phone signs."""

    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("intent_id", "approver_email", name="uq_approvals_intent_approver"),
        Index("ix_approvals_approver_status", "approver_email", "status"),
    )

    approval_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.intent_id"), index=True)
    approver_email: Mapped[str] = mapped_column(String(254))
    nonce: Mapped[str] = mapped_column(String(64), unique=True)
    canonical_summary: Mapped[str | None] = mapped_column(Text)
    summary_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10))  # pending, decided, expired
    decision: Mapped[str | None] = mapped_column(String(15))  # approve, decline, report_fraud
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # M2+: the seniority this approval needs, when it escalates upward if nobody
    # has decided, and which approval it escalated from.
    required_level: Mapped[int | None] = mapped_column(Integer)
    escalate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_from: Mapped[str | None] = mapped_column(String(40))


class Mandate(Base):
    """Written by Prajit's mandate service; GET /mandates/{id} serves `document`
    (the contract's Mandate object) as stored."""

    __tablename__ = "mandates"

    mandate_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.intent_id"), index=True)
    document: Mapped[dict[str, Any]] = mapped_column(JsonType)
    summary_sha256: Mapped[str] = mapped_column(String(64))
    kms_key_version: Mapped[str] = mapped_column(String(300))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrgNode(Base):
    """M2+ organisation tree: group > company > plant > department. `settings`
    may only tighten what the parent allows (lower thresholds, narrower hours)."""

    __tablename__ = "org_nodes"

    node_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("org_nodes.node_id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # group, company, plant, department
    name: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.company_id"))
    settings: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrgRule(Base):
    """A rule on one node, written in CEL over the payment's attributes. When it
    matches, the payment needs at least `min_tier`; `hard_flag` also sends it to
    individual review."""

    __tablename__ = "org_rules"
    __table_args__ = (UniqueConstraint("node_id", "code", name="uq_org_rules_node_code"),)

    rule_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("org_nodes.node_id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(String(300))
    expression: Mapped[str] = mapped_column(Text)
    min_tier: Mapped[int] = mapped_column(Integer)
    hard_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Delegation(Base):
    """Time-boxed delegation. The rule enforced here: never to someone more
    junior. Signing by the delegating approver arrives with the M5 workflow."""

    __tablename__ = "delegations"

    delegation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    delegator_email: Mapped[str] = mapped_column(ForeignKey("approvers.email"), index=True)
    delegate_email: Mapped[str] = mapped_column(ForeignKey("approvers.email"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StandingMandate(Base):
    """A signed standing mandate (Prajit owns the signed format and the gate check).
    The engine reads it to put a payment in the auto-release lane, and keeps the
    usage counters in standing_mandate_usage."""

    __tablename__ = "standing_mandates"

    standing_mandate_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.vendor_id"), index=True)
    payee_account_sha256: Mapped[str] = mapped_column(String(64))
    payee_ifsc: Mapped[str] = mapped_column(String(11))
    cap_per_payment_paise: Mapped[int] = mapped_column(BigInteger)
    cap_per_month_paise: Mapped[int] = mapped_column(BigInteger)
    max_count: Mapped[int] = mapped_column(Integer)
    approver_email: Mapped[str] = mapped_column(String(254))
    signature: Mapped[str | None] = mapped_column(Text)  # Prajit's; verified before insert
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StandingMandateUsage(Base):
    """Monthly total and count per standing mandate, changed only by a single
    conditional UPDATE so two payments can never both slip under the cap."""

    __tablename__ = "standing_mandate_usage"
    __table_args__ = (
        CheckConstraint("total_paise >= 0", name="total_non_negative"),
        CheckConstraint("used_count >= 0", name="count_non_negative"),
    )

    standing_mandate_id: Mapped[str] = mapped_column(
        ForeignKey("standing_mandates.standing_mandate_id"), primary_key=True
    )
    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM in IST
    total_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    used_count: Mapped[int] = mapped_column(Integer, default=0)


class Batch(Base):
    """The batch lane gathered at one approval window, for one approver to sign
    with a single fingerprint (Prajit owns the signed batch format)."""

    __tablename__ = "batches"

    batch_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    department_id: Mapped[str | None] = mapped_column(ForeignKey("org_nodes.node_id"))
    window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    approver_email: Mapped[str] = mapped_column(String(254))
    nonce: Mapped[str] = mapped_column(String(64), unique=True)
    line_count: Mapped[int] = mapped_column(Integer)
    total_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10))  # pending, decided, expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Prajit's signed batch format: the line hashes the signed summary binds.
    line_hashes: Mapped[list[str] | None] = mapped_column(JsonType)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Policy(Base):
    """Versioned policy documents (the contract's PolicySet). Exactly one active
    version per company; publishing a new one never edits an old one."""

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("company_id", "version", name="uq_policies_company_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.company_id"))
    version: Mapped[str] = mapped_column(String(40))
    document: Mapped[dict[str, Any]] = mapped_column(JsonType)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
