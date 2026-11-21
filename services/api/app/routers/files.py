"""POST /v1/files/bank and GET /v1/files/bank/{fileId}.

The file door. A bank payment file is uploaded, and each line becomes an
ordinary payment intent that meets the same gate as everything else.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile, status

from app.domain.models import AuthenticatedUser
from app.roles import require_roles
from app.runtime import Runtime, get_runtime
from app.services.bank_files import BankFileError, bank_file_view, upload_bank_file

router = APIRouter(tags=["files"])

#: Bank files are small: a few hundred payments of a few dozen bytes each. The
#: cap is here so an upload cannot be used to exhaust the service's memory.
MAX_BYTES = 1_000_000


@router.post(
    "/files/bank",
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadBankFile",
)
async def post_bank_file(
    file: Annotated[UploadFile, File(description="CSV, one payment per line")],
    department_id: Annotated[str | None, Form()] = None,
    rt: Runtime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_roles("clerk", "finance")),
):
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise BankFileError(f"A bank file may be at most {MAX_BYTES // 1000} kB.")
    return upload_bank_file(
        rt,
        filename=file.filename or "payments.csv",
        content=content,
        uploaded_by=user.email or user.uid,
        department_id=department_id,
    )


@router.get("/files/bank/{fileId}", operation_id="getBankFile")
def get_bank_file(
    file_id: Annotated[str, Path(alias="fileId", pattern=r"^bf_[A-Za-z0-9]+$")],
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance")),
):
    return bank_file_view(rt, file_id)
