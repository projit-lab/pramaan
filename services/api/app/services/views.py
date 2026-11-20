"""Read helpers shared by the M2 services: the active policy, the vendor master
as the contract's Vendor object, the payment facts for the rules, and the
PaymentIntent / ApprovalSummary shapes from contracts/openapi.yaml."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Approval, PaymentIntent, Policy, Vendor, VendorBankAccount
from app.domain.policy import IST, PolicyDocument
from app.errors import ProblemException

PAID = ("approved", "released")  # a payment that went (or is cleared to go) out


def ist(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite hands back naive UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).isoformat(timespec="seconds")


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def active_policy(s: Session, company_id: str) -> tuple[dict[str, Any], PolicyDocument]:
    row = s.scalar(select(Policy).where(Policy.company_id == company_id, Policy.active.is_(True)))
    if row is None:
        # Fail closed: without a policy nothing can be scored, so nothing is accepted.
        raise ProblemException(503, "No active policy", "No policy is published for this company.")
    return row.document, PolicyDocument.from_contract(row.document)


def current_account(s: Session, vendor_id: str) -> VendorBankAccount | None:
    return s.scalar(
        select(VendorBankAccount)
        .where(VendorBankAccount.vendor_id == vendor_id, VendorBankAccount.valid_to.is_(None))
        .order_by(VendorBankAccount.valid_from.desc())
    )


def bank_changed_at(s: Session, vendor_id: str, account: VendorBankAccount) -> datetime | None:
    """When the current account replaced an earlier one; None if it is the first."""
    earlier = s.scalar(
        select(VendorBankAccount.id).where(
            VendorBankAccount.vendor_id == vendor_id, VendorBankAccount.id != account.id
        )
    )
    return aware(account.valid_from) if earlier is not None else None


def has_paid_vendor(s: Session, vendor_id: str) -> bool:
    return (
        s.scalar(
            select(PaymentIntent.intent_id).where(
                PaymentIntent.vendor_id == vendor_id, PaymentIntent.status.in_(PAID)
            )
        )
        is not None
    )


def has_paid_account(s: Session, account_number: str) -> bool:
    return (
        s.scalar(
            select(PaymentIntent.intent_id).where(
                PaymentIntent.payee_account == account_number, PaymentIntent.status.in_(PAID)
            )
        )
        is not None
    )


def months_of_history(vendor: Vendor, now: datetime) -> int:
    return max(0, (now - aware(vendor.onboarded_at)).days // 30)


def vendor_is_new(s: Session, vendor: Vendor, now: datetime) -> bool:
    return months_of_history(vendor, now) == 0 and not has_paid_vendor(s, vendor.vendor_id)


def vendor_view(s: Session, vendor: Vendor, now: datetime) -> dict[str, Any] | None:
    acct = current_account(s, vendor.vendor_id)
    if acct is None:
        return None
    return {
        "vendor_id": vendor.vendor_id,
        "legal_name": vendor.legal_name,
        "gstin": vendor.gstin,
        "account_last4": acct.account_number[-4:],
        "ifsc": acct.ifsc,
        "bank_changed_at": ist(bank_changed_at(s, vendor.vendor_id, acct)),
        "is_new_payee": vendor_is_new(s, vendor, now),
        "months_of_history": months_of_history(vendor, now),
    }


def intent_view(i: PaymentIntent) -> dict[str, Any]:
    return {
        "intent_id": i.intent_id,
        "status": i.status,
        "tier": i.tier,
        "amount_paise": str(i.amount_paise),
        "currency": i.currency,
        "payer_account_last4": i.payer_account[-4:],
        "payee": {
            "name_at_bank": i.payee_name,
            "account_last4": i.payee_account_last4,
            "ifsc": i.payee_ifsc,
            "vendor_id": i.vendor_id,
        },
        "purpose": i.purpose,
        "invoice_sha256": i.invoice_sha256,
        "instruction_channel": i.instruction_channel,
        "instruction_note": i.instruction_note,
        "initiator": {"type": i.initiator_type, "id": i.initiator_id},
        "reasons": i.reasons,
        "explanation": None,  # M3 (Gemini)
        "model_armor_finding": None,  # M3
        "invoice": None,  # M3
        "policy_version": i.policy_version,
        "approvers": i.approvers,
        # `approval` (signed-approval evidence) arrives with Shoaib's contract change
        # on his branch; add it here when that contract merges.
        "mandate_id": i.mandate_id,
        # M2+
        "department_id": i.department_id,
        "entry_route": i.entry_route,
        "lane": i.lane,
        "decision_trace": i.decision_trace,
        "payee_checks": i.payee_checks,
        "batch_window_at": ist(i.batch_window_at),
        "batch_id": i.batch_id,
        "standing_mandate_id": i.standing_mandate_id,
        "agent_request_id": None,  # M3
        "created_at": ist(i.created_at),
        "updated_at": ist(i.updated_at),
        "expires_at": ist(i.expires_at),
    }


def approval_summary(a: Approval, i: PaymentIntent) -> dict[str, Any]:
    return {
        "approval_id": a.approval_id,
        "intent_id": a.intent_id,
        "tier": i.tier,
        "amount_paise": str(i.amount_paise),
        "payee_name_at_bank": i.payee_name,
        "payee_account_last4": i.payee_account_last4,
        "status": a.status,
        "expires_at": ist(a.expires_at),
    }
