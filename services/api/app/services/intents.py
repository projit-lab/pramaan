"""POST /intents (M2, Danish): validate, score with the policy engine, store,
route held payments to approvers, publish intent.created and intent.decided.

Order of work: everything that must be true together (the intent, its approvals)
is written in one database transaction. Events and pushes go out only after that
commit, so a subscriber never sees an intent the database does not have.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Approval, Company, Device, PaymentIntent, Vendor
from app.domain.ids import new_id
from app.domain.policy import PaymentFacts, approvers_for, evaluate
from app.errors import ProblemException
from app.runtime import Runtime, utc_now
from app.services.views import (
    active_policy,
    bank_changed_at,
    current_account,
    has_paid_account,
    ist,
    vendor_is_new,
)

logger = logging.getLogger("pramaan")

POLICY_ACTOR = {"type": "service", "id": "policy-engine"}


def _problem(status: int, title: str, detail: str, field: str | None = None) -> ProblemException:
    errors = [{"field": field, "detail": detail}] if field else None
    return ProblemException(status, title, detail, errors=errors)


def create_intent(rt: Runtime, body: Any, now: datetime | None = None) -> dict[str, Any]:
    """`body` is the validated IntentCreate request (see routers/intents.py)."""
    now = (now or utc_now(rt)).astimezone(timezone.utc)
    company_id = rt.settings.COMPANY_ID
    ttl = timedelta(hours=rt.settings.APPROVAL_TTL_HOURS)

    with unit_of_work(rt.sessions) as s:
        company = s.get(Company, company_id)
        if company is None:
            raise ProblemException(503, "Company not set up", f"No company {company_id}.")
        _, policy = active_policy(s, company_id)

        if body.payee_vendor_id:
            vendor = s.get(Vendor, body.payee_vendor_id)
            if vendor is None or vendor.company_id != company_id:
                raise _problem(422, "Unknown vendor", "No such vendor.", "payee_vendor_id")
            acct = current_account(s, vendor.vendor_id)
            if acct is None:
                raise _problem(
                    422,
                    "Vendor has no bank account",
                    "Vendor has no account on record.",
                    "payee_vendor_id",
                )
            changed = bank_changed_at(s, vendor.vendor_id, acct)
            payee = dict(
                vendor_id=vendor.vendor_id,
                name=acct.name_at_bank,
                account=acct.account_number,
                last4=acct.account_number[-4:],
                ifsc=acct.ifsc,
            )
            facts_payee = dict(
                payee_is_new=vendor_is_new(s, vendor, now),
                bank_changed_at=changed,
                first_payment_to_current_account=not has_paid_account(s, acct.account_number),
            )
        else:
            p = body.payee
            # A one-off payee arrives with the last four digits only, so it is always
            # treated as new and its full number is unknown to Pramaan.
            payee = dict(
                vendor_id=None,
                name=p.name_at_bank,
                account=None,
                last4=p.account_last4,
                ifsc=p.ifsc,
            )
            facts_payee = dict(
                payee_is_new=True, bank_changed_at=None, first_payment_to_current_account=True
            )

        result = evaluate(
            PaymentFacts(
                amount_paise=body.amount,
                created_at=now,
                instruction_channel=body.instruction_channel,
                initiator_type=body.initiator.type,
                **facts_payee,
            ),
            policy,
        )
        approvers = list(approvers_for(body.amount, policy)) if result.decision == "hold" else []
        intent = PaymentIntent(
            intent_id=new_id("pi"),
            company_id=company_id,
            vendor_id=payee["vendor_id"],
            payee_name=payee["name"],
            payee_account=payee["account"],
            payee_account_last4=payee["last4"],
            payee_ifsc=payee["ifsc"],
            payer_account=company.payer_account,
            amount_paise=body.amount,
            currency="INR",
            purpose=body.purpose,
            invoice_sha256=body.invoice_sha256,
            instruction_channel=body.instruction_channel,
            instruction_note=body.instruction_note,
            initiator_type=body.initiator.type,
            initiator_id=body.initiator.id,
            decision=result.decision,
            status=result.status,
            tier=result.tier,
            reasons=result.reasons,
            policy_version=result.policy_version,
            approvers=approvers,
            created_at=now,
            updated_at=now,
            expires_at=now + ttl if approvers else None,
        )
        s.add(intent)
        s.flush()
        approvals = [
            Approval(
                approval_id=new_id("ap"),
                intent_id=intent.intent_id,
                approver_email=email,
                nonce=secrets.token_urlsafe(24),
                status="pending",
                created_at=now,
                expires_at=now + ttl,
            )
            for email in approvers
        ]
        s.add_all(approvals)
        s.flush()
        devices = {
            a.approval_id: [
                (d.device_id, d.fcm_token)
                for d in s.scalars(
                    select(Device).where(
                        Device.approver_email == a.approver_email,
                        Device.revoked.is_(False),
                        Device.fcm_token.is_not(None),
                    )
                )
            ]
            for a in approvals
        }
        snapshot = _event_payloads(intent, approvals)

    # ---- after commit: events, then pushes -------------------------------------
    bus = rt.event_bus
    bus.publish(
        "intent-created",
        "intent.created",
        company_id,
        intent.intent_id,
        {"type": body.initiator.type, "id": body.initiator.id},
        snapshot["created"],
    )
    bus.publish(
        "intent-decided",
        "intent.decided",
        company_id,
        intent.intent_id,
        POLICY_ACTOR,
        snapshot["decided"],
    )
    _push(rt, intent.intent_id, approvals, devices, now)

    return {
        "intent_id": intent.intent_id,
        "decision": intent.decision,
        "status": intent.status,
        "tier": intent.tier,
        "reasons": intent.reasons,
        "policy_version": intent.policy_version,
        "created_at": ist(now),
    }


def _event_payloads(intent: PaymentIntent, approvals: list[Approval]) -> dict[str, dict]:
    return {
        "created": {
            "amount_paise": str(intent.amount_paise),
            "currency": intent.currency,
            "payee_name": intent.payee_name,
            "payee_account_last4": intent.payee_account_last4,
            "payee_ifsc": intent.payee_ifsc,
            "payer_account_last4": intent.payer_account[-4:],
            "purpose": intent.purpose,
            "invoice_sha256": intent.invoice_sha256,
            "instruction_channel": intent.instruction_channel,
            "initiator": {"type": intent.initiator_type, "id": intent.initiator_id},
        },
        "decided": {
            "decision": intent.decision,
            "status": intent.status,
            "tier": intent.tier,
            "policy_version": intent.policy_version,
            "reasons": [{"code": r["code"], "source": r["source"]} for r in intent.reasons],
            "model_armor_finding": None,
            "approvers": [a.approver_email for a in approvals],
        },
    }


def _push(
    rt: Runtime,
    intent_id: str,
    approvals: list[Approval],
    devices: dict[str, list[tuple[str, str]]],
    now: datetime,
) -> None:
    """Send each approver's phones the 'approval waiting' data message. The
    `pushed` step is written once at least one phone took it."""
    delivered = []
    for a in approvals:
        for device_id, token in devices.get(a.approval_id, []):
            r = rt.notifier.send_approval_waiting(device_id, token, a.approval_id, intent_id)
            if r.ok:
                delivered.append(a.approver_email)
        if not devices.get(a.approval_id):
            logger.warning(f"No enrolled phone with a push token for {a.approver_email}")
    if delivered:
        who = ", ".join(sorted(set(delivered)))
        try:
            # Steps 1-3 (created, scored, held) come from the projector; pushed is 4.
            rt.read_model.set_document(
                f"holds/{intent_id}/steps",
                "04",
                {"n": 4, "step": "pushed", "at": now, "detail": f"Sent to {who}'s phone."},
            )
        except Exception as e:  # the push already went; a missing timeline line is not fatal
            logger.warning(f"Could not write the pushed step for {intent_id}: {type(e).__name__}")
