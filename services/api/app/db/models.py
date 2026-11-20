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
    # AP Manager, Controller, CFO, MD. The M2+ hierarchy uses it; M2 routes by email.
    role: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
