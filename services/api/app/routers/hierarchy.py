"""M2+ routes: the organisation tree (read, and save with the tighten-only check),
the approver hierarchy, the approver's batches, and standing mandates with their
usage. Shoaib's screens read these; the contract additions are proposals in
contracts/openapi.yaml."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Approver, Batch, PaymentIntent, StandingMandate
from app.domain.approver_levels import LEVEL_NAMES
from app.domain.models import AuthenticatedUser
from app.errors import ProblemException
from app.roles import require_email, require_roles
from app.runtime import Runtime, get_runtime, utc_now
from app.services import standing
from app.services.intents import _base_settings
from app.services.org import load_tree, save_node, tree_view
from app.services.views import active_policy, ist

router = APIRouter()


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str | None = None
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,59}$")
    text: str = Field(min_length=1, max_length=300)
    expression: str = Field(min_length=1, max_length=2000)
    min_tier: int = Field(ge=0, le=3)
    hard_flag: bool = False
    enabled: bool = True


class NodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str | None = None
    kind: str | None = None
    name: str | None = Field(default=None, max_length=200)
    settings: dict = Field(default_factory=dict)
    rules: list[RuleIn] = Field(default_factory=list)


@router.get("/org/tree", tags=["policies"], operation_id="getOrgTree")
def get_tree(
    rt: Runtime = Depends(get_runtime), _u: AuthenticatedUser = Depends(require_roles("finance"))
):
    with unit_of_work(rt.sessions) as s:
        return {"nodes": tree_view(load_tree(s))}


@router.put("/org/nodes/{nodeId}", tags=["policies"], operation_id="putOrgNode")
def put_node(
    node_id: Annotated[str, Path(alias="nodeId", pattern=r"^org_[A-Za-z0-9_]+$")],
    body: NodeIn,
    rt: Runtime = Depends(get_runtime),
    _u: AuthenticatedUser = Depends(require_roles("finance")),
):
    with unit_of_work(rt.sessions) as s:
        doc, _ = active_policy(s, rt.settings.COMPANY_ID)
        problems = save_node(
            s, node_id, body, _base_settings(doc), rt.settings.COMPANY_ID, utc_now(rt)
        )
        if problems:
            raise ProblemException(
                422,
                "This change would loosen a parent's rules",
                "Rules can only get stricter further down the organisation.",
                errors=[{"field": "rules", "detail": p} for p in problems],
            )
        return {"nodes": tree_view(load_tree(s))}


@router.get("/approvers", tags=["approvals"], operation_id="listApprovers")
def list_approvers(
    rt: Runtime = Depends(get_runtime), _u: AuthenticatedUser = Depends(require_roles("finance"))
):
    with unit_of_work(rt.sessions) as s:
        rows = s.scalars(
            select(Approver)
            .where(Approver.company_id == rt.settings.COMPANY_ID)
            .order_by(Approver.level.desc(), Approver.email)
        )
        return {
            "approvers": [
                {
                    "email": a.email,
                    "display_name": a.display_name,
                    "role": a.role,
                    "level": a.level,
                    "level_name": LEVEL_NAMES.get(a.level),
                    "node_id": a.node_id,
                    "active": a.active,
                }
                for a in rows
            ]
        }


@router.get("/batches", tags=["approvals"], operation_id="listBatches")
def list_batches(
    status: str | None = Query(default=None, pattern="^(pending|decided|expired)$"),
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    with unit_of_work(rt.sessions) as s:
        q = select(Batch).where(Batch.approver_email == user.email)
        if status:
            q = q.where(Batch.status == status)
        out = []
        for b in s.scalars(q.order_by(Batch.window_at)):
            lines = s.scalars(
                select(PaymentIntent)
                .where(PaymentIntent.batch_id == b.batch_id)
                .order_by(PaymentIntent.amount_paise.desc())
            )
            out.append(
                {
                    "batch_id": b.batch_id,
                    "window_at": ist(b.window_at),
                    "status": b.status,
                    "line_count": b.line_count,
                    "total_paise": str(b.total_paise),
                    "expires_at": ist(b.expires_at),
                    "lines": [
                        {
                            "intent_id": i.intent_id,
                            "amount_paise": str(i.amount_paise),
                            "payee_name_at_bank": i.payee_name,
                            "payee_account_last4": i.payee_account_last4,
                            "tier": i.tier,
                            "checks_passed": bool((i.payee_checks or {}).get("passed")),
                        }
                        for i in lines
                    ],
                }
            )
        return {"batches": out}


@router.get("/standing-mandates", tags=["mandates"], operation_id="listStandingMandates")
def list_standing(
    rt: Runtime = Depends(get_runtime), _u: AuthenticatedUser = Depends(require_roles("finance"))
):
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        out = []
        for sm in s.scalars(
            select(StandingMandate).where(StandingMandate.company_id == rt.settings.COMPANY_ID)
        ):
            total, count = standing.usage(s, sm, now)
            out.append(
                {
                    "standing_mandate_id": sm.standing_mandate_id,
                    "vendor_id": sm.vendor_id,
                    "payee_ifsc": sm.payee_ifsc,
                    "approver": sm.approver_email,
                    "cap_per_payment_paise": str(sm.cap_per_payment_paise),
                    "cap_per_month_paise": str(sm.cap_per_month_paise),
                    "max_count": sm.max_count,
                    "used_this_month_paise": str(total),
                    "used_this_month_count": count,
                    "expires_at": ist(sm.expires_at),
                    "revoked": sm.revoked,
                }
            )
        return {"standing_mandates": out}


@router.post(
    "/standing-mandates/{standingMandateId}/revoke",
    tags=["mandates"],
    operation_id="revokeStandingMandate",
)
def revoke_standing(
    standing_mandate_id: Annotated[
        str, Path(alias="standingMandateId", pattern=r"^sm_[A-Za-z0-9]+$")
    ],
    rt: Runtime = Depends(get_runtime),
    _u: AuthenticatedUser = Depends(require_roles("finance")),
):
    with unit_of_work(rt.sessions) as s:
        sm = s.get(StandingMandate, standing_mandate_id)
        if sm is None or sm.company_id != rt.settings.COMPANY_ID:
            raise ProblemException(404, "Not found", "No such standing mandate.")
        sm.revoked = True  # revoking only ever stops payments, so it needs no signature
        return {"standing_mandate_id": sm.standing_mandate_id, "revoked": True}
