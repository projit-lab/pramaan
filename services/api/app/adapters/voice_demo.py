"""In-memory adapters for DEMO_MODE only.

Stand in for AlloyDB (approvals, voice sessions), Pub/Sub and the Firestore
step writer until those adapters land. Never used in production.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.ids import new_id
from app.domain.voice import ApprovalView

log = logging.getLogger("pramaan.demo")

DEMO_COMPANY = "co_acme"
DEMO_APPROVER = "uid_cfo"


class SeededApprovals:
    """Three approvals: a signed Tier 2, an unsigned Tier 2 and a Tier 1."""

    def __init__(self) -> None:
        self.rows: dict[str, ApprovalView] = {}
        self.reset()

    def reset(self) -> None:
        self.rows = {}
        for name, tier, verified in [("tier2", 2, True), ("tier2_unsigned", 2, False), ("tier1", 1, True)]:
            self.rows[name] = ApprovalView(
                approval_id=new_id("ap"),
                intent_id=new_id("pi"),
                company_id=DEMO_COMPANY,
                nonce=new_id("nonce"),
                tier=tier,
                tier1_verified=verified,
                approver_uid=DEMO_APPROVER,
            )

    def get(self, approval_id: str) -> ApprovalView | None:
        return next((a for a in self.rows.values() if a.approval_id == approval_id), None)


class RecordingEvents:
    """Logs what would go to Pub/Sub and the Firestore steps, and keeps it for /demo/events."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.steps: list[dict[str, str]] = []

    def publish(self, topic: str, envelope: dict[str, Any]) -> None:
        self.published.append({"topic": topic, **envelope})
        log.info("PUBLISH %s %s", topic, json.dumps(envelope))

    def step(self, intent_id: str, step: str, detail: str) -> None:
        self.steps.append({"intent_id": intent_id, "step": step, "detail": detail})
        log.info("STEP %s %s %s", intent_id, step, detail)


def wire_voice_demo(app: Any) -> None:
    """Point the voice router at the in-memory stand-ins.

    Only called when ENV=local, next to the other local-only wiring. In
    production these three become AlloyDB, Pub/Sub and the Firestore step
    writer, and `current_approver_uid` becomes the Firebase ID token plus App
    Check check. Until then the endpoint exists but is not part of the real
    approval flow: that is Phase 6, where the voice step runs only after the
    Tier 1 signature has verified.
    """
    import os
    import secrets as _secrets

    from fastapi import Header

    from app.domain.voice import InMemoryVoiceStore, VoiceService
    from app.routers import voice

    approvals = SeededApprovals()
    events = RecordingEvents()

    def build() -> VoiceService:
        secret = os.environ.get("PRAMAAN_VOICE_SECRET", "").encode() or _secrets.token_bytes(32)
        return VoiceService(
            approvals=approvals, store=InMemoryVoiceStore(), events=events, secret=secret
        )

    state = {"service": build()}
    app.dependency_overrides[voice.get_voice_service] = lambda: state["service"]

    def demo_uid(x_demo_uid: str = Header(...)) -> str:
        # Local stand-in for the Firebase ID token check.
        return x_demo_uid

    app.dependency_overrides[voice.current_approver_uid] = demo_uid

    # Kept out of the served OpenAPI so the contract diff stays clean.
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
        state["service"] = build()
        return {k: v.approval_id for k, v in approvals.rows.items()}
