"""Approvals (M2, Danish): the approver's list, and the decline / report paths.

`block_by_approver` is what Prajit's POST /approvals/{id}/decision calls *after*
it has verified the device signature on a decline or a fraud report. It never
verifies anything itself, and it can only stop money, never release it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Approval, PaymentIntent
from app.errors import ProblemException
from app.runtime import Runtime, utc_now
from app.services.views import approval_summary, aware, ist

BLOCK_REASONS = {"decline": "declined_by_approver", "report_fraud": "reported_fraud"}
STATUS_AFTER = {"decline": "declined", "report_fraud": "blocked"}


def list_approvals(
    rt: Runtime, approver_email: str, status: str | None, now: datetime | None = None
) -> list[dict[str, Any]]:
    """The caller's own approvals, riskiest first. Pending ones past their expiry
    are marked expired on the way out, so the app never offers a dead approval."""
    now = (now or utc_now(rt)).astimezone(timezone.utc)
    with unit_of_work(rt.sessions) as s:
        rows = s.execute(
            select(Approval, PaymentIntent)
            .join(PaymentIntent, PaymentIntent.intent_id == Approval.intent_id)
            .where(Approval.approver_email == approver_email)
        ).all()
        for a, _ in rows:
            if a.status == "pending" and aware(a.expires_at) <= now:
                a.status = "expired"
        out = [approval_summary(a, i) for a, i in rows if status is None or a.status == status]
    out.sort(key=lambda r: (-r["tier"], r["expires_at"] or ""))
    return out


def block_by_approver(
    rt: Runtime,
    approval_id: str,
    approver_email: str,
    decision: str,
    detail: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Decline or report fraud on a held payment. The caller has already verified
    the signature; this records the outcome and stops the payment."""
    if decision not in BLOCK_REASONS:
        raise ProblemException(422, "Not a blocking decision", "Use decline or report_fraud.")
    now = (now or utc_now(rt)).astimezone(timezone.utc)
    with unit_of_work(rt.sessions) as s:
        approval = s.get(Approval, approval_id, with_for_update=True)
        if approval is None or approval.approver_email != approver_email:
            raise ProblemException(404, "Approval not found", "No such approval for this approver.")
        intent = s.get(PaymentIntent, approval.intent_id, with_for_update=True)
        if approval.status != "pending" or aware(approval.expires_at) <= now:
            raise ProblemException(
                409, "Approval no longer open", f"This approval is {approval.status}."
            )
        if intent.status != "held":
            raise ProblemException(
                409, "Payment no longer held", f"The payment is {intent.status}."
            )

        approval.status = "decided"
        approval.decision = decision
        approval.decided_at = now
        # One decline stops the payment, so the other approvers' requests close too.
        for other in s.scalars(
            select(Approval).where(
                Approval.intent_id == intent.intent_id,
                Approval.approval_id != approval_id,
                Approval.status == "pending",
            )
        ):
            other.status = "expired"
        intent.status = STATUS_AFTER[decision]
        intent.decided_by = approver_email
        intent.updated_at = now
        intent_id, company_id, status = intent.intent_id, intent.company_id, intent.status

    reason = BLOCK_REASONS[decision]
    text = detail or (
        f"{approver_email} declined the payment."
        if decision == "decline"
        else f"{approver_email} declined and reported it as fraud."
    )
    rt.event_bus.publish(
        "payment-blocked",
        "payment.blocked",
        company_id,
        intent_id,
        {"type": "human", "id": approver_email},
        {"reason": reason, "detail": text, "mandate_id": None, "blocked_at_step": "signed"},
    )
    try:
        rt.read_model.update_document(
            "holds",
            intent_id,
            {"status": status, "approver": approver_email, "updatedAt": now},
        )
    except Exception:
        # The projector rebuilds the hold from payment.blocked; the event is the record.
        pass
    return {
        "approval_id": approval_id,
        "intent_id": intent_id,
        "status": status,
        "reason": reason,
        "decided_at": ist(now),
    }
