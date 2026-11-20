from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


def test_refuses_to_start_outside_demo_mode(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        main.create_app()


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    return TestClient(main.create_app())


def test_demo_full_flow(demo):
    ids = demo.get("/_demo/voice/approvals").json()
    h = {"X-Demo-Uid": "uid_cfo"}
    s = demo.post(f"/v1/approvals/{ids['tier2']}/voice", json={"action": "start", "language": "ta"}, headers=h).json()
    r = demo.post(
        f"/v1/approvals/{ids['tier2']}/voice",
        json={"action": "complete", "voice_id": s["voice_id"], "digits": s["code"]},
        headers=h,
    ).json()
    assert r["matched"] is True
    ev = demo.get("/_demo/voice/events").json()
    assert [x["step"] for x in ev["steps"]] == ["voice_started", "voice_verified"]
    assert ev["published"][-1]["topic"] == "approval-voice-checked"


def test_demo_requires_caller(demo):
    ids = demo.get("/_demo/voice/approvals").json()
    r = demo.post(f"/v1/approvals/{ids['tier2']}/voice", json={"action": "start", "language": "ta"})
    assert r.status_code == 422  # no X-Demo-Uid


def test_demo_routes_not_in_served_spec(demo):
    paths = demo.get("/openapi.json").json()["paths"]
    assert "/v1/approvals/{approvalId}/voice" in paths
    assert not any(p.startswith("/_demo") or p == "/healthz" for p in paths)
