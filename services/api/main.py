"""Pramaan API (FastAPI on Cloud Run).

So far this holds only the M4 Tier 2 voice step. It runs with in-memory demo
adapters when DEMO_MODE=true. Outside demo mode it refuses to start until the
real pieces are wired: the Firebase ID token + App Check dependency, AlloyDB
for approvals and voice sessions, Pub/Sub, and the Firestore step writer.

    DEMO_MODE=true uvicorn main:create_app --factory --port 8765     (from services/api)
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import FastAPI, Header

from adapters.demo import RecordingEvents, SeededApprovals
from domain.voice import InMemoryVoiceStore, VoiceService
from routers import voice

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="Pramaan API", version="0.4.0")

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(voice.router)

    if os.environ.get("DEMO_MODE") == "true":
        _wire_demo(app)
    else:
        # Fail closed: never serve approvals without real auth and storage.
        raise RuntimeError(
            "Only DEMO_MODE=true is wired so far. Production needs the Firebase ID token + "
            "App Check dependency, AlloyDB, Pub/Sub and the Firestore step writer."
        )
    return app


def _wire_demo(app: FastAPI) -> None:
    approvals = SeededApprovals()
    events = RecordingEvents()
    state = {"service": _demo_service(approvals, events)}

    app.dependency_overrides[voice.get_voice_service] = lambda: state["service"]

    def demo_uid(x_demo_uid: str = Header(...)) -> str:
        # DEMO_MODE stand-in for the Firebase ID token check.
        return x_demo_uid

    app.dependency_overrides[voice.current_approver_uid] = demo_uid

    # Dev-only helpers, kept out of the served OpenAPI so the contract diff stays clean.
    @app.get("/_demo/voice/approvals", include_in_schema=False)
    def demo_approvals() -> dict[str, str]:
        return {k: v.approval_id for k, v in approvals.rows.items()}

    @app.get("/_demo/voice/events", include_in_schema=False)
    def demo_events() -> dict[str, list]:
        return {"published": events.published, "steps": events.steps}

    @app.post("/_demo/voice/reset", include_in_schema=False)
    def demo_reset() -> dict[str, str]:
        approvals.reset()
        events.published.clear()
        events.steps.clear()
        state["service"] = _demo_service(approvals, events)
        return {k: v.approval_id for k, v in approvals.rows.items()}


def _demo_service(approvals: SeededApprovals, events: RecordingEvents) -> VoiceService:
    secret = os.environ.get("PRAMAAN_VOICE_SECRET", "").encode() or secrets.token_bytes(32)
    return VoiceService(approvals=approvals, store=InMemoryVoiceStore(), events=events, secret=secret)
