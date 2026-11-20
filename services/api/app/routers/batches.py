"""Signed batches (Prajit): one fingerprint approves a window's Tier 1 lines.

GET  /v1/batches/{batchId}           the batch summary to sign, with its lines
POST /v1/batches/{batchId}/decision  verify the phone's signature, then issue one
                                     mandate per line (or block every line)

The server rebuilds everything from stored payments. The phone's request carries
only the decision and the signature. See app/domain/batch.py for the format.
"""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Any, Literal

from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.adapters.signer import get_mandate_signer
from app.db.engine import unit_of_work
from app.db.models import Batch, Device, Mandate, PaymentIntent
from app.domain.batch import MAX_BATCH_TIER, batch_summary_fields, line_hash
from app.domain.canonical import canonical_bytes
from app.domain.device_signature import SignatureInvalid, verify_device_signature
from app.domain.ids import new_id
from app.domain.mandate import build_mandate
from app.domain.models import AuthenticatedUser
from app.errors import ProblemException
from app.roles import require_email
from app.runtime import Runtime, get_runtime, utc_now
from app.services.views import aware, ist

router = APIRouter(tags=["approvals"])

BatchId = Annotated[str, Path(alias="batchId", pattern=r"^bt_[A-Za-z0-9]+$")]

# Play Integrity is not wired yet (M5). Say so in the mandate rather than claim a verdict.
INTEGRITY_NOT_EVALUATED = "NOT_EVALUATED"


class BatchDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "decline"]
    signature: str = Field(min_length=1)


def _load(s, batch_id: str, email: str) -> tuple[Batch, list[PaymentIntent]]:
    batch = s.get(Batch, batch_id, with_for_update=True)
    if batch is None or batch.approver_email != email:
        raise ProblemException(404, "Batch not found", "No such batch for this approver.")
    lines = list(
        s.scalars(
            select(PaymentIntent)
            .where(PaymentIntent.batch_id == batch_id)
            .order_by(PaymentIntent.intent_id)
        )
    )
    if not lines:
        raise ProblemException(409, "Empty batch", "This batch has no payments.")
    for i in lines:
        if i.tier > MAX_BATCH_TIER:
            raise ProblemException(
                422,
                "Batch holds a payment that needs individual review",
                f"{i.intent_id} is Tier {i.tier}. Tier 2 and 3 payments are never batched.",
                type_="https://pramaan.example/problems/tier-not-batchable",
            )
    return batch, lines


def _summary(batch: Batch, lines: list[PaymentIntent]) -> tuple[dict[str, str], list[str]]:
    expires = ist(batch.expires_at) or ""
    hashes = [line_hash(i, batch.nonce, expires) for i in lines]
    fields = batch_summary_fields(
        batch_id=batch.batch_id,
        approver=batch.approver_email,
        line_hashes=hashes,
        total_paise=sum(i.amount_paise for i in lines),
        nonce=batch.nonce,
        expires_at=expires,
        window_at=ist(batch.window_at) or "",
    )
    return fields, hashes


def _check_open(batch: Batch, lines: list[PaymentIntent], now: datetime) -> None:
    if batch.status != "pending" or aware(batch.expires_at) <= now:
        raise ProblemException(409, "Batch no longer open", f"This batch is {batch.status}.")
    not_held = [i.intent_id for i in lines if i.status != "held"]
    if not_held:
        raise ProblemException(
            409, "Batch changed", f"These payments are no longer held: {', '.join(not_held)}."
        )


def _line_view(i: PaymentIntent) -> dict[str, Any]:
    return {
        "intent_id": i.intent_id,
        "payee_name": i.payee_name,
        "payee_account_last4": i.payee_account_last4,
        "payee_ifsc": i.payee_ifsc,
        "amount_paise": str(i.amount_paise),
        "purpose": i.purpose or "",
        "tier": i.tier,
    }


@router.get("/batches/{batchId}", operation_id="getBatch")
def get_batch(
    batch_id: BatchId,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        batch, lines = _load(s, batch_id, user.email)
        _check_open(batch, lines, now)
        fields, hashes = _summary(batch, lines)
        batch.line_hashes = hashes
        return {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "window_at": ist(batch.window_at),
            "expires_at": ist(batch.expires_at),
            "line_count": len(lines),
            "total_paise": fields["total_paise"],
            "lines": [_line_view(i) for i in lines],
            "summary_fields": fields,
            "canonical_b64": base64.b64encode(canonical_bytes(fields)).decode("ascii"),
        }


@router.post("/batches/{batchId}/decision", operation_id="decideBatch")
def decide_batch(
    batch_id: BatchId,
    body: BatchDecisionIn,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
) -> dict[str, Any]:
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        batch, lines = _load(s, batch_id, user.email)
        _check_open(batch, lines, now)
        # Rebuild on the server from the payments as they are now; never trust the phone.
        fields, hashes = _summary(batch, lines)
        if batch.line_hashes is not None and batch.line_hashes != hashes:
            raise ProblemException(
                409, "Batch changed", "A payment changed since the batch was shown. Reload it."
            )

        device = s.scalar(
            select(Device).where(Device.approver_email == user.email, Device.revoked.is_(False))
        )
        if device is None or not device.public_key_pem:
            raise ProblemException(409, "No active device", "No enrolled device for this approver.")
        spki = serialization.load_pem_public_key(device.public_key_pem.encode()).public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        try:
            signature_der = base64.b64decode(body.signature, validate=True)
            verify_device_signature(spki, canonical_bytes(fields), signature_der)
        except (SignatureInvalid, ValueError) as exc:
            raise ProblemException(
                422,
                "Device signature invalid",
                str(exc),
                type_="https://pramaan.example/problems/signature-invalid",
            ) from exc

        # Single use: the batch closes now, whatever the decision.
        batch.status = "decided"
        batch.signed_at = now
        batch.line_hashes = hashes

        events: list[tuple[str, str, str, dict[str, Any]]] = []
        mandates: list[dict[str, str]] = []
        if body.decision == "decline":
            for i in lines:
                i.status = "declined"
                i.decided_by = user.email
                i.updated_at = now
                events.append(
                    (
                        "payment-blocked",
                        "payment.blocked",
                        i.intent_id,
                        {
                            "reason": "declined_by_approver",
                            "detail": f"{user.email} declined batch {batch_id}.",
                            "mandate_id": None,
                            "blocked_at_step": "signed",
                        },
                    )
                )
        else:
            signer = get_mandate_signer(rt.settings)
            for i in lines:
                mandate_id = new_id("pm")
                doc = build_mandate(
                    summary_fields=fields,
                    device_spki_der=spki,
                    device_signature_der=signature_der,
                    approval_facts={
                        "mandate_id": mandate_id,
                        "intent_id": i.intent_id,
                        "decision": "approve",
                        "tier": i.tier,
                        "policy_version": i.policy_version,
                        "device_id": device.device_id,
                        "approver": user.email,
                        "key_security_level": device.key_security_level,
                        "patch_level": device.patch_level,
                        "integrity_verdict": INTEGRITY_NOT_EVALUATED,
                        "expires_at": batch.expires_at,
                        "payer": {
                            "company": rt.settings.COMPANY_ID,
                            "account_last4": i.payer_account[-4:],
                        },
                        "payee": {
                            "name_at_bank": i.payee_name,
                            "account_last4": i.payee_account_last4,
                            "ifsc": i.payee_ifsc,
                            "vendor_id": i.vendor_id,
                        },
                        "amount_paise": str(i.amount_paise),
                        "currency": i.currency,
                        "purpose": {"invoice": i.purpose, "invoice_sha256": i.invoice_sha256},
                        "initiator": {"type": i.initiator_type, "id": i.initiator_id},
                    },
                    signer=signer,
                    now=now,
                )
                s.add(
                    Mandate(
                        mandate_id=mandate_id,
                        intent_id=i.intent_id,
                        document=doc.to_dict(),
                        summary_sha256=doc.summary_sha256,
                        kms_key_version=doc.countersignature["kms_key_version"],
                        expires_at=datetime.fromisoformat(doc.expires_at),
                        used_at=None,
                        created_at=now,
                    )
                )
                i.mandate_id = mandate_id
                i.status = "approved"
                i.decided_by = user.email
                i.updated_at = now
                mandates.append({"intent_id": i.intent_id, "mandate_id": mandate_id})
                events.append(
                    (
                        "mandate-issued",
                        "mandate.issued",
                        i.intent_id,
                        {
                            "mandate_id": mandate_id,
                            "summary_sha256": doc.summary_sha256,
                            "kms_key_version": doc.countersignature["kms_key_version"],
                            "tier": i.tier,
                            "expires_at": doc.expires_at,
                            "batch_id": batch_id,
                        },
                    )
                )
        status_after = "approved" if body.decision == "approve" else "declined"
        intent_ids = [i.intent_id for i in lines]

    actor = {"type": "human", "id": user.email}
    for topic, etype, intent_id, data in events:
        rt.event_bus.publish(topic, etype, rt.settings.COMPANY_ID, intent_id, actor, data)
    for intent_id in intent_ids:
        try:
            rt.read_model.update_document(
                "holds",
                intent_id,
                {"status": status_after, "approver": user.email, "updatedAt": now},
            )
        except Exception:
            pass  # the projector rebuilds holds from the events
    return {
        "batch_id": batch_id,
        "decision": body.decision,
        "verified": True,
        "line_count": len(intent_ids),
        "mandates": mandates,
    }
