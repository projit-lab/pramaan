"""ENV=local only: drive the decline / report path without a phone.

In every other environment a decline arrives through Prajit's signed
POST /approvals/{id}/decision. This route is not mounted outside ENV=local and is
left out of the served OpenAPI, so it can never reach dev, demo or production."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.domain.models import AuthenticatedUser
from app.roles import require_email
from app.runtime import Runtime, get_runtime
from app.services.approvals import block_by_approver

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
