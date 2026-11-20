"""ENV=local only: drive paths that otherwise need a phone, a signature or a
scheduler.

- decline / report: in every other environment this arrives through Prajit's
  signed POST /approvals/{id}/decision.
- the M2+ jobs (close batches, escalate): Cloud Scheduler calls them in the cloud.
- a standing mandate without a signature, and a delegation: Prajit's signed
  formats and the M5 workflow replace these.

None of these routes is mounted outside ENV=local, and all are left out of the
served OpenAPI, so they can never reach dev, demo or production."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db.engine import unit_of_work
from app.db.models import Delegation, PaymentIntent, StandingMandate, Vendor
from app.domain.ids import new_id
from app.domain.models import AuthenticatedUser
from app.domain.money import parse_paise
from app.errors import ProblemException
from app.roles import require_email, require_roles
from app.runtime import Runtime, get_runtime, utc_now
from app.services import jobs, standing
from app.services.approvals import block_by_approver
from app.services.org import check_delegation
from app.services.views import current_account

router = APIRouter(include_in_schema=False)


class LocalDecision(BaseModel):
    decision: Literal["decline", "report_fraud"]


@router.post("/_local/approvals/{approval_id}/block")
def local_block(
    approval_id: str,
    body: LocalDecision,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    return block_by_approver(rt, approval_id, user.email, body.decision)


class LocalJob(BaseModel):
    at: datetime | None = None  # pretend it is this time (default: now)


@router.post("/_local/jobs/close-batches")
def local_close_batches(
    body: LocalJob,
    rt: Runtime = Depends(get_runtime),
    _u: AuthenticatedUser = Depends(require_roles("finance")),
):
    return {"batches": jobs.close_due_batches(rt, body.at)}


@router.post("/_local/jobs/escalate")
def local_escalate(
    body: LocalJob,
    rt: Runtime = Depends(get_runtime),
    _u: AuthenticatedUser = Depends(require_roles("finance")),
):
    return {"escalated": jobs.escalate_overdue(rt, body.at)}


class LocalStanding(BaseModel):
    vendor_id: str
    cap_per_payment_paise: str
    cap_per_month_paise: str
    max_count: int = Field(ge=1)
    days: int = Field(default=30, ge=1, le=366)


@router.post("/_local/standing-mandates")
def local_standing(
    body: LocalStanding,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        vendor = s.get(Vendor, body.vendor_id)
        acct = current_account(s, body.vendor_id) if vendor else None
        if acct is None:
            raise ProblemException(422, "Unknown vendor", "No such vendor with an account.")
        sm = StandingMandate(
            standing_mandate_id=new_id("sm"),
            company_id=rt.settings.COMPANY_ID,
            vendor_id=vendor.vendor_id,
            payee_account_sha256=standing.account_hash(acct.account_number),
            payee_ifsc=acct.ifsc,
            cap_per_payment_paise=parse_paise(body.cap_per_payment_paise),
            cap_per_month_paise=parse_paise(body.cap_per_month_paise),
            max_count=body.max_count,
            approver_email=user.email,
            signature=None,
            revoked=False,
            created_at=now,
            expires_at=now + timedelta(days=body.days),
        )
        s.add(sm)
        return {"standing_mandate_id": sm.standing_mandate_id}


class LocalDelegation(BaseModel):
    delegate_email: str
    hours: int = Field(default=24, ge=1, le=24 * 30)


@router.post("/_local/delegations")
def local_delegation(
    body: LocalDelegation,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        check_delegation(s, user.email, body.delegate_email)
        d = Delegation(
            delegation_id=new_id("dl"),
            delegator_email=user.email,
            delegate_email=body.delegate_email,
            valid_from=now,
            valid_to=now + timedelta(hours=body.hours),
            created_at=now,
        )
        s.add(d)
        return {"delegation_id": d.delegation_id}


@router.post("/_local/intents/{intent_id}/tamper")
def local_tamper_intent(
    intent_id: str,
    rt: Runtime = Depends(get_runtime),
):
    if rt.settings.ENV != "local":
        raise ProblemException(404, "Not found", "Route only available when ENV=local.")
    with unit_of_work(rt.sessions) as s:
        intent = s.get(PaymentIntent, intent_id, with_for_update=True)
        if intent is None:
            raise ProblemException(404, "Not found", f"No payment intent '{intent_id}'.")
        # Alter one digit of stored payee account
        if intent.payee_account:
            last = intent.payee_account[-1]
            new_last = "9" if last != "9" else "8"
            intent.payee_account = intent.payee_account[:-1] + new_last
        else:
            intent.payee_account = "9999999999"
        intent.updated_at = utc_now(rt)
        return {"intent_id": intent.intent_id, "payee_account": intent.payee_account}
