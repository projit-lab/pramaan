"""Approvals router (M1 & M2).

Endpoints:
- GET /v1/approvals: list pending approvals for caller (Danish, M2)
- GET /v1/approvals/{id}: get approval with canonical summary (Prajit, M1)
- POST /v1/approvals/{id}/decision: verify device signature, build mandate or block (Prajit, M1)
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.adapters.signer import get_mandate_signer
from app.db.engine import unit_of_work
from app.db.models import Approval, Device, Mandate, PaymentIntent
from app.domain.canonical import canonical_bytes
from app.domain.device_signature import SignatureInvalid, verify_device_signature
from app.domain.ids import new_id
from app.domain.mandate import build_mandate
from app.domain.models import AuthenticatedUser
from app.errors import ProblemException
from app.roles import require_email
from app.runtime import Runtime, get_runtime, utc_now
from app.services.approvals import block_by_approver, list_approvals
from app.services.views import approval_view, aware, ist

CONSUMED = "used:"
PENDING_VOICE = "pending_voice"

router = APIRouter(tags=["approvals"])


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decision: Literal["approve", "decline", "report_fraud"]
    signature: str = Field(min_length=1)  # base64 DER signature from phone


@router.get("/approvals", operation_id="listApprovals")
def get_approvals(
    status: Literal["pending", "decided", "expired"] | None = Query(default=None),
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    return {"approvals": list_approvals(rt, user.email, status)}


@router.get("/approvals/{approvalId}", operation_id="getApproval")
def get_approval(
    approval_id: Annotated[str, Path(alias="approvalId", pattern=r"^ap_[A-Za-z0-9]+$")],
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    """Retrieve approval with canonical payment summary fields and fresh single-use nonce."""
    with unit_of_work(rt.sessions) as s:
        approval = s.get(Approval, approval_id)
        if approval is None or approval.approver_email != user.email:
            raise ProblemException(404, "Approval not found", "No such approval for this approver.")

        intent = s.get(PaymentIntent, approval.intent_id)
        if intent is None:
            raise ProblemException(
                404, "Payment intent not found", "Intent associated with approval missing."
            )

        # Fresh single-use signing nonce bound to this approval
        nonce = secrets.token_urlsafe(24)
        approval.nonce = nonce

        summary_fields: dict[str, str] = {
            "amount_paise": str(intent.amount_paise),
            "currency": str(intent.currency or "INR"),
            "expires_at": ist(approval.expires_at) or "",
            "initiator": f"{intent.initiator_type}:{intent.initiator_id}",
            "intent_id": intent.intent_id,
            "invoice_sha256": intent.invoice_sha256 or "",
            "nonce": nonce,
            "payee_account": intent.payee_account or intent.payee_account_last4,
            "payee_ifsc": intent.payee_ifsc,
            "payee_name": intent.payee_name,
            "payer_account": intent.payer_account,
            "purpose": intent.purpose or "",
            "v": "1",
        }

        c_bytes = canonical_bytes(summary_fields)
        canonical_b64 = base64.b64encode(c_bytes).decode("ascii")
        summary_sha256 = hashlib.sha256(c_bytes).hexdigest().lower()

        approval.canonical_summary = json.dumps(summary_fields, ensure_ascii=False)
        approval.summary_sha256 = summary_sha256

        return approval_view(approval, intent, summary_fields, canonical_b64)


@router.post("/approvals/{approvalId}/decision", operation_id="decideApproval")
def decide_approval(
    approval_id: Annotated[str, Path(alias="approvalId", pattern=r"^ap_[A-Za-z0-9]+$")],
    body: DecisionIn,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    """Verify device signature against server-recomputed canonical summary and decide."""
    now = utc_now(rt)

    with unit_of_work(rt.sessions) as s:
        approval = s.get(Approval, approval_id, with_for_update=True)
        if approval is None or approval.approver_email != user.email:
            raise ProblemException(404, "Approval not found", "No such approval for this approver.")

        intent = s.get(PaymentIntent, approval.intent_id, with_for_update=True)
        if intent is None:
            raise ProblemException(
                404, "Payment intent not found", "Intent associated with approval missing."
            )

        if approval.status != "pending" or aware(approval.expires_at) <= now:
            raise ProblemException(
                409, "Approval no longer open", f"This approval is {approval.status}."
            )
        if intent.status != "held":
            raise ProblemException(
                409, "Payment no longer held", f"The payment is {intent.status}."
            )

        if not approval.nonce or approval.nonce.startswith(CONSUMED):
            raise ProblemException(
                409, "Nonce already consumed", "This signing nonce has already been consumed."
            )

        # Check caller's enrolled device
        device = s.scalar(
            select(Device).where(Device.approver_email == user.email, Device.revoked.is_(False))
        )
        if device is None:
            raise ProblemException(
                409, "No active device", "No enrolled active device found for this approver."
            )
        if not device.public_key_pem:
            raise ProblemException(
                422, "Device public key missing", "Enrolled device is missing public key."
            )

        # Rebuild canonical summary on the SERVER from stored intent + issued nonce
        server_summary_fields: dict[str, str] = {
            "amount_paise": str(intent.amount_paise),
            "currency": str(intent.currency or "INR"),
            "expires_at": ist(approval.expires_at) or "",
            "initiator": f"{intent.initiator_type}:{intent.initiator_id}",
            "intent_id": intent.intent_id,
            "invoice_sha256": intent.invoice_sha256 or "",
            "nonce": approval.nonce,
            "payee_account": intent.payee_account or intent.payee_account_last4,
            "payee_ifsc": intent.payee_ifsc,
            "payee_name": intent.payee_name,
            "payer_account": intent.payer_account,
            "purpose": intent.purpose or "",
            "v": "1",
        }
        server_canonical_bytes = canonical_bytes(server_summary_fields)

        # Verify device signature
        pubkey = serialization.load_pem_public_key(device.public_key_pem.encode("utf-8"))
        device_spki_der = pubkey.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        try:
            signature_der = base64.b64decode(body.signature)
        except Exception as exc:
            raise ProblemException(
                422, "Malformed signature", f"Failed decoding base64 signature: {exc}"
            ) from exc

        try:
            verify_device_signature(device_spki_der, server_canonical_bytes, signature_der)
        except SignatureInvalid as exc:
            raise ProblemException(
                422,
                "Device signature invalid",
                str(exc),
                type_="https://pramaan.example/problems/signature-invalid",
            ) from exc

        # Consume the single-use nonce immediately
        # Unique column: mark it used with a unique value, never a shared empty string.
        approval.nonce = CONSUMED + secrets.token_urlsafe(16)

        voice_required = (
            body.decision == "approve" and intent.tier >= 2 and rt.settings.VOICE_STEP_ENABLED
        )
        if voice_required:
            approval.decision = PENDING_VOICE
            approval.pending_signature_b64 = base64.b64encode(signature_der).decode("ascii")
            approval.pending_summary = json.dumps(server_summary_fields, ensure_ascii=False)

        # If declining or reporting fraud, defer to Danish's block_by_approver
        if body.decision in ("decline", "report_fraud"):
            approval_id_val = approval.approval_id
            decision_val = body.decision

    if body.decision in ("decline", "report_fraud"):
        res = block_by_approver(rt, approval_id_val, user.email, decision_val, now=now)
        return {
            "approval_id": approval_id_val,
            "decision": decision_val,
            "mandate_id": None,
            "verified": True,
            "status": res["status"],
        }

    # Tier 2 and above: the signature is verified, but the mandate waits for the
    # spoken-code check. It can only add a check, never replace the signature.
    if voice_required:
        return {
            "approval_id": approval_id,
            "decision": "approve",
            "mandate_id": None,
            "verified": True,
            "status": "pending_voice",
            "next": "voice",
        }

    return issue_mandate(
        rt, approval_id, user.email, server_summary_fields, device_spki_der, signature_der, now
    )


def issue_mandate(
    rt: Runtime,
    approval_id: str,
    approver_email: str,
    server_summary_fields: dict[str, str],
    device_spki_der: bytes,
    signature_der: bytes,
    now: datetime,
) -> dict[str, Any]:
    """Build, store and announce the KMS-countersigned mandate for a verified approval.

    Called straight after the signature check (Tier 0-1), or, for Tier 2+, only once
    the spoken-code check has passed (app/services/voice_flow.py)."""
    with unit_of_work(rt.sessions) as s:
        approval = s.get(Approval, approval_id, with_for_update=True)
        intent = s.get(PaymentIntent, approval.intent_id, with_for_update=True)
        device = s.scalar(
            select(Device).where(Device.approver_email == approver_email, Device.revoked.is_(False))
        )

        signer = get_mandate_signer(rt.settings)
        mandate_id = new_id("pm")

        mandate_doc = build_mandate(
            summary_fields=server_summary_fields,
            device_spki_der=device_spki_der,
            device_signature_der=signature_der,
            approval_facts={
                "mandate_id": mandate_id,
                "intent_id": intent.intent_id,
                "decision": "approve",
                "tier": intent.tier,
                "policy_version": intent.policy_version,
                "device_id": device.device_id,
                "approver": approver_email,
                "key_security_level": device.key_security_level,
                "patch_level": device.patch_level,
                "integrity_verdict": "NOT_EVALUATED",
                "expires_at": intent.expires_at
                or (now + timedelta(hours=rt.settings.APPROVAL_TTL_HOURS)),
                "payer": {
                    "company": rt.settings.COMPANY_ID,
                    "account_last4": intent.payer_account[-4:],
                },
                "payee": {
                    "name_at_bank": intent.payee_name,
                    "account_last4": intent.payee_account_last4,
                    "ifsc": intent.payee_ifsc,
                    "vendor_id": intent.vendor_id,
                },
                "amount_paise": str(intent.amount_paise),
                "currency": intent.currency,
                "purpose": {"invoice": intent.purpose, "invoice_sha256": intent.invoice_sha256},
                "initiator": {"type": intent.initiator_type, "id": intent.initiator_id},
            },
            signer=signer,
            now=now,
        )

        mandate_row = Mandate(
            mandate_id=mandate_id,
            intent_id=intent.intent_id,
            document=mandate_doc.to_dict(),
            summary_sha256=mandate_doc.summary_sha256,
            kms_key_version=mandate_doc.countersignature["kms_key_version"],
            expires_at=datetime.fromisoformat(mandate_doc.expires_at),
            used_at=None,
            created_at=now,
        )
        s.add(mandate_row)

        intent.mandate_id = mandate_id
        intent.status = "approved"
        intent.decided_by = approver_email
        intent.updated_at = now

        approval.status = "decided"
        approval.decision = "approve"
        approval.decided_at = now

        # Other approvals on same intent are marked expired
        for other in s.scalars(
            select(Approval).where(
                Approval.intent_id == intent.intent_id,
                Approval.approval_id != approval_id,
                Approval.status == "pending",
            )
        ):
            other.status = "expired"

        intent_id_val = intent.intent_id
        device_id_val = device.device_id
        device_sec_level = device.key_security_level
        device_patch_level = device.patch_level
        intent_tier = intent.tier
        kms_key_version_val = mandate_doc.countersignature["kms_key_version"]
        mandate_expires_at_val = mandate_doc.expires_at
        summary_sha256_val = mandate_doc.summary_sha256

    # Publish events
    rt.event_bus.publish(
        topic="approval-signed",
        event_type="approval.signed",
        company_id=rt.settings.COMPANY_ID,
        intent_id=intent_id_val,
        actor={"type": "human", "id": approver_email},
        data={
            "approval_id": approval_id,
            "approver": approver_email,
            "decision": "approve",
            "device_id": device_id_val,
            "key_security_level": device_sec_level,
            "patch_level": device_patch_level,
            "device_integrity": "NOT_EVALUATED",
            "summary_sha256": summary_sha256_val,
            "verified": True,
        },
    )

    rt.event_bus.publish(
        topic="mandate-issued",
        event_type="mandate.issued",
        company_id=rt.settings.COMPANY_ID,
        intent_id=intent_id_val,
        actor={"type": "service", "id": "mandate_signer"},
        data={
            "mandate_id": mandate_id,
            "summary_sha256": summary_sha256_val,
            "kms_key_version": kms_key_version_val,
            "tier": intent_tier,
            "expires_at": mandate_expires_at_val,
        },
    )

    # Update read model
    try:
        rt.read_model.update_document(
            "holds",
            intent_id_val,
            {
                "status": "approved",
                "approver": approver_email,
                "mandateId": mandate_id,
                "updatedAt": now,
            },
        )
    except Exception:
        pass

    return {
        "approval_id": approval_id,
        "decision": "approve",
        "mandate_id": mandate_id,
        "verified": True,
    }
