"""Tier 2 in the real approval flow: signature first, then the spoken code, then the mandate.

POST /approvals/{id}/decision verifies the phone signature and, for Tier 2 and above,
parks it on the approval (decision = pending_voice) instead of issuing the mandate.
The approver then completes the spoken-code step (Gemini Live on the phone turns the
spoken code into digits; this server compares them). Only when that passes is the
mandate issued, from the signature that was already verified. Three wrong tries
block the payment and fall back to a call-back.

The voice step can only ADD a check: there is no path from a spoken code to a
mandate without a verified signature already parked on the approval.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import serialization
from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Approval, Device, PaymentIntent
from app.domain.voice import ApprovalView

logger = logging.getLogger("pramaan")

PENDING_VOICE = "pending_voice"


class DbApprovals:
    """ApprovalLookup over the real approvals table. The approver's identity is their
    email (the same identity the decision endpoint uses)."""

    def __init__(self, rt: Any) -> None:
        self.rt = rt

    def get(self, approval_id: str) -> ApprovalView | None:
        with unit_of_work(self.rt.sessions) as s:
            a = s.get(Approval, approval_id)
            if a is None:
                return None
            intent = s.get(PaymentIntent, a.intent_id)
            if intent is None:
                return None
            return ApprovalView(
                approval_id=a.approval_id,
                intent_id=a.intent_id,
                company_id=intent.company_id,
                nonce=a.nonce or "",
                tier=intent.tier,
                tier1_verified=a.decision == PENDING_VOICE and bool(a.pending_signature_b64),
                approver_uid=a.approver_email,
            )


class CombinedApprovals:
    """Real approvals first; the seeded demo approvals keep the standalone voice demo working."""

    def __init__(self, *lookups: Any) -> None:
        self.lookups = lookups

    def get(self, approval_id: str) -> ApprovalView | None:
        for lookup in self.lookups:
            found = lookup.get(approval_id)
            if found is not None:
                return found
        return None


class FlowEvents:
    """Forwards to the demo recorder, and finishes the real approval when the code passes."""

    def __init__(self, rt: Any, recorder: Any) -> None:
        self.rt = rt
        self.recorder = recorder

    def publish(self, topic: str, envelope: dict[str, Any]) -> None:
        self.recorder.publish(topic, envelope)
        try:
            self.rt.event_bus.publish(
                topic,
                envelope.get("event_type", "approval.voice_checked"),
                self.rt.settings.COMPANY_ID,
                envelope.get("intent_id", ""),
                envelope.get("actor", {"type": "human", "id": "approver"}),
                envelope.get("data", {}),
            )
        except Exception:  # the recorder has it; the bus is best effort here
            pass

    def step(self, intent_id: str, step: str, detail: str) -> None:
        self.recorder.step(intent_id, step, detail)
        if step == "voice_verified":
            finish_after_voice(self.rt, intent_id)
        elif step == "voice_failed" and detail.startswith("Three wrong tries"):
            block_after_voice(self.rt, intent_id)


def _pending(s: Any, intent_id: str) -> Approval | None:
    return s.scalar(
        select(Approval).where(
            Approval.intent_id == intent_id,
            Approval.decision == PENDING_VOICE,
            Approval.status == "pending",
        )
    )


def finish_after_voice(rt: Any, intent_id: str) -> dict[str, Any] | None:
    """Issue the mandate from the signature that was verified before the voice step."""
    from app.routers.approvals import issue_mandate  # avoid an import cycle

    with unit_of_work(rt.sessions) as s:
        a = _pending(s, intent_id)
        if a is None:
            return None  # a seeded demo approval, or already finished
        device = s.scalar(
            select(Device).where(
                Device.approver_email == a.approver_email, Device.revoked.is_(False)
            )
        )
        if device is None or not device.public_key_pem:
            logger.warning(f"Voice passed for {intent_id} but no active device; not issuing")
            return None
        spki = serialization.load_pem_public_key(device.public_key_pem.encode()).public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        approval_id, email = a.approval_id, a.approver_email
        summary = json.loads(a.pending_summary or "{}")
        signature = base64.b64decode(a.pending_signature_b64 or "")
        a.pending_signature_b64 = None
    return issue_mandate(
        rt, approval_id, email, summary, spki, signature, datetime.now(timezone.utc)
    )


def block_after_voice(rt: Any, intent_id: str) -> None:
    now = datetime.now(timezone.utc)
    with unit_of_work(rt.sessions) as s:
        a = _pending(s, intent_id)
        if a is None:
            return
        a.status = "decided"
        a.decision = "voice_failed"
        a.decided_at = now
        a.pending_signature_b64 = None
        intent = s.get(PaymentIntent, intent_id)
        if intent is not None and intent.status == "held":
            intent.status = "blocked"
            intent.updated_at = now
    rt.event_bus.publish(
        "payment-blocked",
        "payment.blocked",
        rt.settings.COMPANY_ID,
        intent_id,
        {"type": "service", "id": "voice_step"},
        {
            "reason": "voice_check_failed",
            "detail": "Three wrong spoken codes. Falls back to a call-back.",
            "mandate_id": None,
            "blocked_at_step": "signed",
        },
    )
    try:
        rt.read_model.update_document("holds", intent_id, {"status": "blocked", "updatedAt": now})
    except Exception:
        pass
