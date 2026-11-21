"""GET /v1/vendors and GET /v1/policies (contracts/openapi.yaml). Read-only in M2."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.engine import unit_of_work
from app.db.models import Vendor
from app.domain.models import AuthenticatedUser
from app.roles import require_roles
from app.runtime import Runtime, get_runtime, utc_now
from app.services.views import active_policy, vendor_view

router = APIRouter()


@router.get("/vendors", tags=["vendors"], operation_id="listVendors")
def list_vendors(
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("finance", "clerk")),
):
    now = utc_now(rt)
    with unit_of_work(rt.sessions) as s:
        vendors = s.scalars(
            select(Vendor)
            .where(Vendor.company_id == rt.settings.COMPANY_ID)
            .order_by(Vendor.legal_name)
        )
        return {"vendors": [v for v in (vendor_view(s, x, now) for x in vendors) if v]}


@router.get("/policies", tags=["policies"], operation_id="getPolicies")
def get_policies(
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("finance", "clerk")),
):
    with unit_of_work(rt.sessions) as s:
        doc, _ = active_policy(s, rt.settings.COMPANY_ID)
        return doc
