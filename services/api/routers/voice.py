"""POST /v1/approvals/{approvalId}/voice (contracts/openapi.yaml, operationId approvalVoice)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from domain.voice import VoiceError, VoiceResult, VoiceService, ist

PROBLEM_BASE = "https://pramaan.example/problems/"

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


# Both are wired in main.py. In production they come from the Firebase ID token
# check plus the App Check token (X-Firebase-AppCheck); tests override them.
def get_voice_service() -> VoiceService:  # pragma: no cover - replaced at startup
    raise NotImplementedError("wire VoiceService in main.py")


def current_approver_uid() -> str:  # pragma: no cover - replaced at startup
    raise NotImplementedError("wire the Firebase ID token + App Check dependency")


class VoiceStart(BaseModel):
    action: Literal["start"]
    language: Literal["ta", "hi", "en"]


class VoiceComplete(BaseModel):
    action: Literal["complete"]
    voice_id: str = Field(pattern=r"^vs_[A-Za-z0-9]+$")
    digits: str = Field(pattern=r"^[0-9]{6}$")


def state(r: VoiceResult) -> dict[str, Any]:
    s = r.session
    out: dict[str, Any] = {
        "approval_id": s.approval_id,
        "voice_id": s.voice_id,
        "status": s.status.value,
        "matched": r.matched,
        "attempts_remaining": r.attempts_remaining,
        "language": s.language,
        "expires_at": ist(s.expires_at),
    }
    if r.code is not None:
        out["code"] = r.code
    return out


def problem(status: int, slug: str, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": PROBLEM_BASE + slug, "title": title, "status": status, "detail": detail},
    )


@router.post("/{approvalId}/voice", operation_id="approvalVoice")
def approval_voice(
    approval_id: Annotated[str, Path(alias="approvalId", pattern=r"^ap_[A-Za-z0-9]+$")],
    body: Annotated[Union[VoiceStart, VoiceComplete], Field(discriminator="action")],
    service: Annotated[VoiceService, Depends(get_voice_service)],
    uid: Annotated[str, Depends(current_approver_uid)],
):
    try:
        if isinstance(body, VoiceStart):
            result = service.start(approval_id, uid, body.language)
        else:
            result = service.complete(approval_id, uid, body.voice_id, body.digits)
    except VoiceError as e:
        return problem(e.status, e.slug, e.title, e.detail)
    return state(result)
