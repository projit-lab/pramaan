"""In-memory adapters for DEMO_MODE only.

Stand in for AlloyDB (approvals, voice sessions), Pub/Sub and the Firestore
step writer until those adapters land. Never used in production.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from domain.ids import new_id
from domain.voice import ApprovalView

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
