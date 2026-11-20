"""Keeps the voice step in line with contracts/ so drift fails here, not in the demo."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.domain.voice import EVENT_TOPIC, EVENT_TYPE, LANGUAGES, VoiceStatus

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
VOICE_STEPS = {"voice_started", "voice_verified", "voice_failed"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))


def test_endpoint_defined(spec):
    op = spec["paths"]["/approvals/{approvalId}/voice"]["post"]
    assert op["operationId"] == "approvalVoice"
    assert {"200", "401", "404", "409", "422"} <= set(op["responses"])


def test_response_fields_match_router(spec):
    from app.routers.voice import state
    from app.domain.voice import VoiceResult, VoiceSession
    from datetime import datetime, timezone

    schema = spec["components"]["schemas"]["VoiceStepState"]
    s = VoiceSession("vs_1", "ap_1", "pi_1", "co_1", "n", "ta", b"", datetime.now(timezone.utc), VoiceStatus.AWAITING_CODE)
    out = state(VoiceResult(s, code="123456"))
    assert set(schema["required"]) <= set(out)
    assert set(out) <= set(schema["properties"])
    assert set(schema["properties"]["status"]["enum"]) == {v.value for v in VoiceStatus}


def test_languages_match(spec):
    assert set(spec["components"]["schemas"]["VoiceLanguage"]["enum"]) == LANGUAGES


def test_step_names_in_contract(spec):
    steps = set(spec["components"]["schemas"]["Step"]["properties"]["step"]["enum"])
    assert VOICE_STEPS <= steps
    firestore = (CONTRACTS / "firestore.md").read_text(encoding="utf-8")
    events = (CONTRACTS / "events.md").read_text(encoding="utf-8")
    for step in VOICE_STEPS:
        assert f"`{step}`" in firestore
        assert f"`{step}`" in events


def test_event_topic_in_contract():
    events = (CONTRACTS / "events.md").read_text(encoding="utf-8")
    assert re.search(rf"\|\s*`{EVENT_TOPIC}`\s*\|\s*`{re.escape(EVENT_TYPE)}`", events)


def test_web_step_type_knows_voice_steps():
    ts = (CONTRACTS.parent / "web" / "shared" / "src" / "types" / "firestore.ts").read_text(encoding="utf-8")
    for step in VOICE_STEPS:
        assert f"'{step}'" in ts
