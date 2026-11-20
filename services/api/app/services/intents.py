"""POST /intents: validate, score, sort into a lane, store, route, publish.

M2 (Danish): validation, storage, policy engine v1, events, push.
M2+ (Danish): the department's place in the organisation tree tightens the
thresholds, the automatic payee checks run, every CEL rule from the root to the
department is evaluated (strictest wins), the lane sorter picks individual
review, the batch lane or auto-release, and held payments go to the nearest
approver of the level the tier needs.

Order of work: everything that must be true together (the intent, its approvals,
a standing-mandate counter) is written in one database transaction. Events and
pushes go out only after that commit, so a subscriber never sees an intent the
database does not have.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.adapters.bank_lookup import MockBankLookup
from app.db.engine import unit_of_work
from app.db.models import Approval, Company, Device, PaymentIntent, Vendor
from app.domain.approver_levels import LEVEL_NAMES, route
from app.domain.hierarchy import RuleError, evaluate_hierarchy, path_to
from app.domain.ids import new_id
from app.domain.lanes import AUTO_RELEASE, BATCH, LaneInput, next_window, sort_lane, unusual_amount
from app.domain.payee_checks import invoice_match, look_alike, name_check
from app.domain.policy import IST, PaymentFacts, evaluate
from app.errors import ProblemException
from app.runtime import Runtime, utc_now
from app.services import standing
from app.services.org import active_delegates, load_people, load_tree
from app.services.views import (
    PAID,
    active_policy,
    aware,
    bank_changed_at,
    current_account,
    has_paid_account,
    ist,
    months_of_history,
    vendor_is_new,
)

logger = logging.getLogger("pramaan")

POLICY_ACTOR = {"type": "service", "id": "policy-engine"}
BANK = MockBankLookup()

CHECK_REASONS = {
    "name_check_mismatch": "The name the bank holds for this account does not match the payee.",
    "name_check_not_found": "The bank could not confirm a name for this account.",
    "look_alike": "The payee's name looks like another vendor's ({of}).",
    "invoice_mismatch": "The invoice does not match the vendor master ({fields}).",
    "unusual_amount": "Far above anything paid to this payee before.",
}


def _problem(status: int, title: str, detail: str, field: str | None = None) -> ProblemException:
    errors = [{"field": field, "detail": detail}] if field else None
    return ProblemException(status, title, detail, errors=errors)


def _base_settings(doc: dict[str, Any]) -> dict[str, Any]:
    th = doc["tier_thresholds_paise"]
    return {
        "tier1_paise": int(th["tier1"]),
        "tier2_paise": int(th["tier2"]),
        "tier3_paise": int(th["tier3"]),
        "working_hours_ist": doc.get("working_hours_ist") or {"start": "09:00", "end": "19:00"},
        "approval_windows_ist": doc.get("approval_windows_ist") or ["11:00", "16:00"],
    }


def create_intent(rt: Runtime, body: Any, now: datetime | None = None) -> dict[str, Any]:
    """`body` is the validated IntentCreate request (see routers/intents.py)."""
    now = (now or utc_now(rt)).astimezone(timezone.utc)
    cfg = rt.settings
    company_id = cfg.COMPANY_ID
    ttl = timedelta(hours=cfg.APPROVAL_TTL_HOURS)

    with unit_of_work(rt.sessions) as s:
        company = s.get(Company, company_id)
        if company is None:
            raise ProblemException(503, "Company not set up", f"No company {company_id}.")
        policy_doc, policy = active_policy(s, company_id)
        base = _base_settings(policy_doc)

        # ---- where in the organisation this payment sits ------------------------
        tree = load_tree(s)
        department_id = body.department_id or cfg.DEFAULT_DEPARTMENT_ID
        if department_id not in tree or tree[department_id].kind != "department":
            raise _problem(422, "Unknown department", "No such department.", "department_id")
        try:
            path = path_to(department_id, tree)
        except RuleError as e:
            raise ProblemException(503, "Organisation tree is broken", str(e)) from e
        path_ids = [n.node_id for n in path]

        # ---- the payee -------------------------------------------------------------
        vendor_info: dict[str, Any] | None = None
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
                legal_name=vendor.legal_name,
                account=acct.account_number,
                last4=acct.account_number[-4:],
                ifsc=acct.ifsc,
            )
            is_new = vendor_is_new(s, vendor, now)
            facts_payee = dict(
                payee_is_new=is_new,
                bank_changed_at=changed,
                first_payment_to_current_account=not has_paid_account(s, acct.account_number),
            )
            paid = list(
                s.scalars(
                    select(PaymentIntent.amount_paise).where(
                        PaymentIntent.vendor_id == vendor.vendor_id, PaymentIntent.status.in_(PAID)
                    )
                )
            )
            others = [
                (v.vendor_id, v.legal_name)
                for v in s.scalars(select(Vendor).where(Vendor.company_id == company_id))
                if aware(v.onboarded_at) < aware(vendor.onboarded_at)
            ]
            vendor_info = {
                "account_last4": payee["last4"],
                "ifsc": acct.ifsc,
                "gstin": vendor.gstin,
            }
            history_months = months_of_history(vendor, now)
        else:
            p = body.payee
            # A one-off payee arrives with the last four digits only, so it is always
            # treated as new and its full number is unknown to Pramaan.
            payee = dict(
                vendor_id=None,
                name=p.name_at_bank,
                legal_name=p.name_at_bank,
                account=None,
                last4=p.account_last4,
                ifsc=p.ifsc,
            )
            is_new, changed, paid, history_months = True, None, [], 0
            facts_payee = dict(
                payee_is_new=True, bank_changed_at=None, first_payment_to_current_account=True
            )
            others = [
                (v.vendor_id, v.legal_name)
                for v in s.scalars(select(Vendor).where(Vendor.company_id == company_id))
            ]

        # ---- policy v1 with the department's tightened settings ----------------------
        eff = _effective(path, base)
        hours = eff["working_hours_ist"]
        dept_policy = replace(
            policy,
            tier1_paise=eff["tier1_paise"],
            tier2_paise=eff["tier2_paise"],
            tier3_paise=eff["tier3_paise"],
            working_start=time.fromisoformat(hours["start"]),
            working_end=time.fromisoformat(hours["end"]),
        )
        v1 = evaluate(
            PaymentFacts(
                amount_paise=body.amount,
                created_at=now,
                instruction_channel=body.instruction_channel,
                initiator_type=body.initiator.type,
                **facts_payee,
            ),
            dept_policy,
        )

        # ---- automatic payee checks ----------------------------------------------------
        bank_name = BANK.name_for(s, payee["account"], payee["ifsc"])
        name_result = name_check(payee["legal_name"], bank_name)
        alike, alike_of, alike_score = look_alike(payee["legal_name"], payee["vendor_id"], others)
        inv_result, inv_fields = invoice_match(
            getattr(body, "invoice", None), vendor_info, body.amount
        )
        unusual = unusual_amount(body.amount, paid)
        checks = {
            "name_check": name_result,
            "bank_name": bank_name,
            "look_alike": alike,
            "look_alike_of": alike_of,
            "look_alike_score": round(alike_score, 3),
            "invoice_match": inv_result,
            "invoice_mismatches": list(inv_fields),
            "unusual_amount": unusual,
        }
        checks["passed"] = name_result == "match" and not alike and inv_result != "mismatch"

        # ---- hierarchy rules (CEL), strictest wins ---------------------------------------
        attributes = {
            "amount_paise": body.amount,
            "currency": "INR",
            "channel": body.instruction_channel,
            "entry_route": body.route,
            "initiator_type": body.initiator.type,
            "hour_ist": now.astimezone(IST).hour,
            "weekday_ist": now.astimezone(IST).isoweekday(),
            "tier_v1": v1.tier,
            "reason_codes": v1.codes,
            "payee": {
                "is_new": is_new,
                "known": payee["vendor_id"] is not None and not is_new,
                "vendor_id": payee["vendor_id"] or "",
                "months_of_history": history_months,
                "bank_changed_days": -1 if changed is None else (now - changed).days,
            },
            "checks": {
                "name_check": name_result,
                "look_alike": alike,
                "invoice_match": inv_result,
                "passed": checks["passed"],
            },
            "history": {"paid_count": len(paid), "max_paid_paise": max(paid, default=0)},
            "signals": {"pressure_language": False, "model_armor_finding": False},  # M3
        }
        hier = evaluate_hierarchy(department_id, tree, attributes, base)
        tier = max(v1.tier, hier.tier_floor)

        reasons = list(v1.reasons)
        for code, ok in (
            (f"name_check_{name_result}", name_result == "match"),
            ("look_alike", not alike),
            ("invoice_mismatch", inv_result != "mismatch"),
            ("unusual_amount", not unusual),
        ):
            if not ok:
                text = CHECK_REASONS[code].format(of=alike_of, fields=", ".join(inv_fields))
                reasons.append({"code": code, "text": text, "source": "rule"})
        seen = {r["code"] for r in reasons}
        for hit in hier.hits:
            if hit.code not in seen:
                reasons.append({"code": hit.code, "text": hit.text, "source": "rule"})
                seen.add(hit.code)

        # ---- the lane --------------------------------------------------------------------
        payee_known = payee["vendor_id"] is not None and not is_new
        sm = None
        if payee_known and payee["account"]:
            sm = standing.find_valid(s, payee["vendor_id"], acct, body.amount, now)

        def sort(standing_ok: bool):
            return sort_lane(
                LaneInput(
                    tier=tier,
                    payee_known=payee_known,
                    reason_codes=tuple(v1.codes),
                    checks_passed=checks["passed"],
                    name_check=name_result,
                    look_alike=alike,
                    invoice_match=inv_result,
                    unusual_amount=unusual,
                    standing_mandate_ok=standing_ok,
                    hierarchy_hard_flags=hier.hard_flags,
                )
            )

        lane = sort(sm is not None)
        if lane.row == 2 and not standing.reserve(s, sm, body.amount, now):
            sm, lane = None, sort(False)  # the cap was used up first; sort again without it
        if lane.row != 2:
            sm = None

        # ---- routing -----------------------------------------------------------------------
        decision, status = (
            ("release", "approved") if lane.lane == AUTO_RELEASE else ("hold", "held")
        )
        window = (
            next_window(now, eff.get("approval_windows_ist") or ("11:00", "16:00"))
            if lane.lane == BATCH
            else None
        )
        assignees: list[tuple[str, int]] = []  # (email, required level)
        if lane.lane not in (AUTO_RELEASE, BATCH):
            people = load_people(s, company_id)
            try:
                chosen = route(path_ids, people, max(tier, 1))
            except LookupError as e:
                # Fail closed: never accept a payment nobody is set up to approve.
                raise ProblemException(503, "No approver for this payment", str(e)) from e
            levels = [p.level for p in chosen]
            for person, needed in zip(chosen, levels, strict=True):
                assignees.append((person.email, needed))
                for delegate in active_delegates(s, person.email, now):
                    d = next((p for p in people if p.email == delegate), None)
                    if d and d.level >= needed and delegate not in {a for a, _ in assignees}:
                        assignees.append((delegate, needed))

        trace = {
            "department": " > ".join(n.name for n in path),
            "tier_v1": v1.tier,
            "tier_floor": hier.tier_floor,
            "rules": [h.as_trace() for h in hier.hits],
            "lane": {
                "lane": lane.lane,
                "row": lane.row,
                "why": lane.why,
                "hard_flags": list(lane.hard_flags),
            },
            "effective": {k: eff[k] for k in ("tier1_paise", "tier2_paise", "tier3_paise")},
            "required_levels": [LEVEL_NAMES[lv] for _, lv in assignees],
        }
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
            entry_route=body.route,
            instruction_note=body.instruction_note,
            initiator_type=body.initiator.type,
            initiator_id=body.initiator.id,
            decision=decision,
            status=status,
            tier=tier,
            reasons=reasons,
            policy_version=v1.policy_version,
            approvers=[a for a, _ in assignees],
            created_at=now,
            updated_at=now,
            expires_at=now + ttl if decision == "hold" else None,
            department_id=department_id,
            lane=lane.lane,
            decision_trace=trace,
            payee_checks=checks,
            batch_window_at=window,
            standing_mandate_id=sm.standing_mandate_id if sm else None,
        )
        s.add(intent)
        s.flush()
        escalate = timedelta(hours=cfg.ESCALATE_AFTER_HOURS)
        approvals = [
            Approval(
                approval_id=new_id("ap"),
                intent_id=intent.intent_id,
                approver_email=email,
                nonce=secrets.token_urlsafe(24),
                status="pending",
                created_at=now,
                expires_at=now + ttl,
                required_level=level,
                # Tier 3 names the CFO and the MD; there is nobody above to escalate to.
                escalate_at=None if tier >= 3 else now + escalate,
            )
            for email, level in assignees
        ]
        s.add_all(approvals)
        s.flush()
        devices = phones_for(s, [(a.approval_id, a.approver_email) for a in approvals])
        snapshot = _event_payloads(intent, approvals)

    # ---- after commit: events, then pushes -------------------------------------------
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
    push(rt, intent.intent_id, [(a.approval_id, a.approver_email) for a in approvals], devices, now)

    return {
        "intent_id": intent.intent_id,
        "decision": intent.decision,
        "status": intent.status,
        "tier": intent.tier,
        "reasons": intent.reasons,
        "policy_version": intent.policy_version,
        "lane": intent.lane,
        "decision_trace": intent.decision_trace,
        "batch_window_at": ist(window),
        "created_at": ist(now),
    }


def _effective(path, base):
    from app.domain.hierarchy import effective_settings

    return effective_settings(path, base)


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
            "entry_route": intent.entry_route,
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
            "lane": intent.lane,
        },
    }


def phones_for(s, approvals: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """approval_id -> [(device_id, fcm_token)] for each approver's live phones."""
    return {
        approval_id: [
            (d.device_id, d.fcm_token)
            for d in s.scalars(
                select(Device).where(
                    Device.approver_email == email,
                    Device.revoked.is_(False),
                    Device.fcm_token.is_not(None),
                )
            )
        ]
        for approval_id, email in approvals
    }


def push(
    rt: Runtime,
    intent_id: str,
    approvals: list[tuple[str, str]],
    devices: dict[str, list[tuple[str, str]]],
    now: datetime,
    step: bool = True,
) -> None:
    """Send each approver's phones the 'approval waiting' data message. The
    `pushed` step is written once at least one phone took it."""
    delivered = []
    for approval_id, email in approvals:
        for device_id, token in devices.get(approval_id, []):
            if rt.notifier.send_approval_waiting(device_id, token, approval_id, intent_id).ok:
                delivered.append(email)
        if not devices.get(approval_id):
            logger.warning(f"No enrolled phone with a push token for {email}")
    if delivered and step:
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
