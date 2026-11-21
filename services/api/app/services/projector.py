"""Write the console's `holds/{intentId}` document when a payment is created.

In the cloud the projector service builds holds from Pub/Sub events. Local and demo-sandbox
runs have no projector (the event bus is in memory), so the console would stay empty. This
writes the same camelCase document, per contracts/firestore.md, straight after an intent is
stored; the later status updates (approved, released, blocked) already update it in place.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("pramaan")

LANE_NAMES = {"individual": "individual_review", "batch": "batch", "auto_release": "auto_release"}


def hold_document(intent: Any) -> dict[str, Any]:
    lane = LANE_NAMES.get(intent.lane or "", None)
    if lane == "auto_release" and intent.standing_mandate_id:
        lane = "auto_release_standing"
    return {
        "intentId": intent.intent_id,
        "status": intent.status,
        "tier": intent.tier,
        "amountPaise": str(intent.amount_paise),
        "currency": intent.currency or "INR",
        "payeeNameAtBank": intent.payee_name,
        "payeeAccountLast4": intent.payee_account_last4,
        "payeeIfsc": intent.payee_ifsc,
        "payerAccountLast4": (intent.payer_account or "")[-4:],
        "purpose": intent.purpose,
        "instructionChannel": intent.instruction_channel,
        "instructionNote": intent.instruction_note,
        "initiator": {"type": intent.initiator_type, "id": intent.initiator_id},
        "reasons": [
            {"code": r.get("code"), "text": r.get("text"), "source": r.get("source", "rule")}
            for r in (intent.reasons or [])
        ],
        "policyVersion": intent.policy_version,
        "approvers": list(intent.approvers or []),
        "approver": None,
        "entryRoute": intent.entry_route,
        "lane": lane,
        "payeeChecks": intent.payee_checks,
        "standingMandateId": intent.standing_mandate_id,
        "batchId": intent.batch_id,
        "mandateId": intent.mandate_id,
        "createdAt": intent.created_at,
        "updatedAt": intent.updated_at,
        "expiresAt": intent.expires_at,
    }


def project_new_intent(rt: Any, intent: Any) -> None:
    try:
        rt.read_model.set_document("holds", intent.intent_id, hold_document(intent))
        steps = [(1, "created", "Payment created."), (2, "scored", f"Tier {intent.tier}.")]
        if intent.status == "held":
            steps.append((3, "held", "Held until the approver signs."))
        for n, step, detail in steps:
            rt.read_model.set_document(
                f"holds/{intent.intent_id}/steps",
                f"{n:02d}",
                {"n": n, "step": step, "at": intent.created_at, "detail": detail},
            )
    except Exception as e:  # the console is a view; never fail the payment over it
        logger.warning(f"Could not project hold {intent.intent_id}: {type(e).__name__}: {e}")
