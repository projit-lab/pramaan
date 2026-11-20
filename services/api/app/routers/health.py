from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    env: str
    version: str


@router.get("/health", response_model=HealthResponse)
@router.get("/healthz", response_model=HealthResponse)
async def get_health():
    """Service health check returning status, env, and git short SHA version."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        env=settings.ENV,
        version=settings.VERSION,
    )
