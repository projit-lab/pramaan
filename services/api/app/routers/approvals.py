"""GET /v1/approvals?status=pending (contracts/openapi.yaml, listApprovals).

Approvals are always the caller's own: the list is filtered by the signed-in
approver's email, never by a query parameter."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.domain.models import AuthenticatedUser
from app.roles import require_email
from app.runtime import Runtime, get_runtime
from app.services.approvals import list_approvals

router = APIRouter(tags=["approvals"])


@router.get("/approvals", operation_id="listApprovals")
def get_approvals(
    status: Literal["pending", "decided", "expired"] | None = Query(default=None),
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_email),
):
    return {"approvals": list_approvals(rt, user.email, status)}
