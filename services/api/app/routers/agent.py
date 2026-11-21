"""POST /v1/agent/invoices: hand the AI payables agent an invoice PDF."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.domain.models import AuthenticatedUser
from app.roles import require_roles
from app.runtime import Runtime, get_runtime
from app.services.agent import MAX_PDF_BYTES, process_invoice

router = APIRouter(tags=["agent"])


@router.post("/agent/invoices", status_code=status.HTTP_201_CREATED, operation_id="agentInvoice")
async def post_agent_invoice(
    file: UploadFile = File(...),
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance", "agent")),
):
    pdf = await file.read(MAX_PDF_BYTES + 1)
    return process_invoice(rt, pdf, file.filename)
