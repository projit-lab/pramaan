"""M2+ scheduled work (Danish). In the cloud, Cloud Scheduler calls these every
few minutes; locally they run through the ENV=local routes.

close_due_batches: at each approval window, gather the batch-lane payments of a
department into one batch for one approver (AP Manager or above), to be signed
with a single fingerprint. Prajit owns the signed batch format and the gate's
check that a line is inside the signed batch and unused.

escalate_overdue: an approval nobody has decided by its escalate_at goes to the
next more senior approver too. The original request stays open; whoever decides
first decides. Tier 3 never escalates: it names the CFO and the MD.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Approval, Batch, PaymentIntent
from app.domain.approver_levels import AP_MANAGER, Person, escalate_to, route
from app.domain.hierarchy import path_to
from app.domain.ids import new_id
from app.runtime import Runtime, utc_now
from app.services.intents import phones_for, push
from app.services.org import load_people, load_tree
from app.services.views import aware, ist


def close_due_batches(rt: Runtime, now: datetime | None = None) -> list[dict[str, Any]]:
    now = aware(now or utc_now(rt)).astimezone(timezone.utc)
    ttl = timedelta(hours=rt.settings.APPROVAL_TTL_HOURS)
    made: list[tuple[Batch, list[str]]] = []
    with unit_of_work(rt.sessions) as s:
        due = [
            i
            for i in s.scalars(
                select(PaymentIntent).where(
                    PaymentIntent.company_id == rt.settings.COMPANY_ID,
                    PaymentIntent.lane == "batch",
                    PaymentIntent.status == "held",
                    PaymentIntent.batch_id.is_(None),
                )
            )
            if i.batch_window_at is not None and aware(i.batch_window_at) <= now
        ]
        if not due:
            return []
        tree = load_tree(s)
        people = load_people(s, rt.settings.COMPANY_ID)
        groups: dict[tuple[str | None, datetime], list[PaymentIntent]] = {}
        for i in due:
            groups.setdefault((i.department_id, aware(i.batch_window_at)), []).append(i)
        for (department_id, window), lines in sorted(
            groups.items(), key=lambda g: (g[0][1], g[0][0] or "")
        ):
            path_ids = [n.node_id for n in path_to(department_id, tree)] if department_id else []
            approver = route(path_ids, people, AP_MANAGER)[0]
            batch = Batch(
                batch_id=new_id("bt"),
                company_id=rt.settings.COMPANY_ID,
                department_id=department_id,
                window_at=window,
                approver_email=approver.email,
                nonce=secrets.token_urlsafe(24),
                line_count=len(lines),
                total_paise=sum(i.amount_paise for i in lines),
                status="pending",
                created_at=now,
                expires_at=now + ttl,
            )
            s.add(batch)
            for i in lines:
                i.batch_id = batch.batch_id
                i.approvers = [approver.email]
                i.updated_at = now
            made.append((batch, [i.intent_id for i in lines]))
        s.flush()
        devices = phones_for(s, [(b.batch_id, b.approver_email) for b, _ in made])

    out = []
    for batch, intent_ids in made:
        # The push names the batch; the app fetches the lines over the API.
        push(rt, batch.batch_id, [(batch.batch_id, batch.approver_email)], devices, now, step=False)
        out.append(
            {
                "batch_id": batch.batch_id,
                "approver": batch.approver_email,
                "lines": len(intent_ids),
                "window_at": ist(batch.window_at),
            }
        )
    return out


def escalate_overdue(rt: Runtime, now: datetime | None = None) -> list[dict[str, Any]]:
    now = aware(now or utc_now(rt)).astimezone(timezone.utc)
    escalate = timedelta(hours=rt.settings.ESCALATE_AFTER_HOURS)
    created: list[tuple[Approval, str]] = []
    with unit_of_work(rt.sessions) as s:
        overdue = [
            a
            for a in s.scalars(
                select(Approval).where(
                    Approval.status == "pending", Approval.escalate_at.is_not(None)
                )
            )
            if aware(a.escalate_at) <= now and aware(a.expires_at) > now
        ]
        if not overdue:
            return []
        tree = load_tree(s)
        people = load_people(s, rt.settings.COMPANY_ID)
        by_email = {p.email: p for p in people}
        for a in overdue:
            intent = s.get(PaymentIntent, a.intent_id)
            a.escalate_at = None  # escalate each request once
            if intent.status != "held" or intent.tier >= 3:
                continue
            path_ids = (
                [n.node_id for n in path_to(intent.department_id, tree)]
                if intent.department_id
                else []
            )
            asked = set(intent.approvers or [])
            current = by_email.get(a.approver_email) or Person(
                a.approver_email, a.required_level or 1, None
            )
            up = escalate_to(current, path_ids, people, asked)
            if up is None:
                continue
            new = Approval(
                approval_id=new_id("ap"),
                intent_id=intent.intent_id,
                approver_email=up.email,
                nonce=secrets.token_urlsafe(24),
                status="pending",
                created_at=now,
                expires_at=a.expires_at,
                required_level=a.required_level,
                escalate_at=now + escalate,
                escalated_from=a.approval_id,
            )
            s.add(new)
            intent.approvers = [*intent.approvers, up.email]
            intent.updated_at = now
            created.append((new, intent.intent_id))
        s.flush()
        devices = phones_for(s, [(n.approval_id, n.approver_email) for n, _ in created])

    for new, intent_id in created:
        push(rt, intent_id, [(new.approval_id, new.approver_email)], devices, now, step=False)
    return [
        {
            "approval_id": n.approval_id,
            "intent_id": i,
            "approver": n.approver_email,
            "escalated_from": n.escalated_from,
        }
        for n, i in created
    ]
