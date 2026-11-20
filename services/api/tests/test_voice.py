from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.ids import new_id
from domain.voice import (
    EVENT_TOPIC,
    EVENT_TYPE,
    ApprovalView,
    InMemoryVoiceStore,
    VoiceError,
    VoiceService,
    VoiceStatus,
    digits_hash,
)
from routers import voice as voice_router

T0 = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)
APPROVER = "uid_cfo"


class Clock:
    def __init__(self) -> None:
        self.t = T0

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kw) -> None:
        self.t += timedelta(**kw)


class Approvals:
    def __init__(self) -> None:
        self.rows: dict[str, ApprovalView] = {}

    def add(self, tier: int = 2, verified: bool = True) -> ApprovalView:
        a = ApprovalView(new_id("ap"), new_id("pi"), "co_acme", "q7Zp-nonce", tier, verified, APPROVER)
        self.rows[a.approval_id] = a
        return a

    def get(self, approval_id: str) -> ApprovalView | None:
        return self.rows.get(approval_id)


class Events:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.steps: list[tuple[str, str]] = []

    def publish(self, topic: str, envelope: dict) -> None:
        self.published.append((topic, envelope))

    def step(self, intent_id: str, step: str, detail: str) -> None:
        self.steps.append((step, detail))

    @property
    def last(self) -> dict:
        return self.published[-1][1]


class Codes:
    def __init__(self, *codes: str) -> None:
        self.codes = list(codes)

    def __call__(self) -> str:
        return self.codes.pop(0)


@pytest.fixture
def env():
    clock, approvals, events = Clock(), Approvals(), Events()
    svc = VoiceService(
        approvals=approvals,
        store=InMemoryVoiceStore(),
        events=events,
        secret=b"test-secret",
        now=clock,
        code_factory=Codes("482913", "105577", "000042", "999999"),
    )
    return svc, approvals, events, clock


def test_exact_match_passes(env):
    svc, approvals, events, _ = env
    a = approvals.add()
    started = svc.start(a.approval_id, APPROVER, "ta")
    assert started.code == "482913"
    assert started.session.status is VoiceStatus.AWAITING_CODE
    done = svc.complete(a.approval_id, APPROVER, started.session.voice_id, "482913")
    assert done.session.status is VoiceStatus.PASSED and done.matched
    assert svc.is_tier2_passed(a.approval_id)
    assert events.last["data"]["result"] == "passed"
    assert ("voice_verified", "Spoken code matched (ta)") in events.steps


def test_code_is_single_use(env):
    svc, approvals, _, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "en").session
    svc.complete(a.approval_id, APPROVER, s.voice_id, "482913")
    with pytest.raises(VoiceError) as e:
        svc.complete(a.approval_id, APPROVER, s.voice_id, "482913")
    assert e.value.slug == "voice-finished"
    with pytest.raises(VoiceError):
        svc.start(a.approval_id, APPROVER, "en")


def test_expires_after_two_minutes(env):
    svc, approvals, events, clock = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "hi").session
    clock.advance(minutes=2)
    r = svc.complete(a.approval_id, APPROVER, s.voice_id, "482913")
    assert r.session.status is VoiceStatus.EXPIRED and not r.matched
    assert not svc.is_tier2_passed(a.approval_id)
    assert events.last["data"]["result"] == "expired"


def test_just_inside_expiry_passes(env):
    svc, approvals, _, clock = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "hi").session
    clock.advance(seconds=119)
    assert svc.complete(a.approval_id, APPROVER, s.voice_id, "482913").session.status is VoiceStatus.PASSED


def test_three_wrong_tries_fall_back_to_callback(env):
    svc, approvals, events, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "ta").session
    r1 = svc.complete(a.approval_id, APPROVER, s.voice_id, "111111")
    assert (r1.session.status, r1.attempts_remaining) == (VoiceStatus.RETRY, 2)
    r2 = svc.complete(a.approval_id, APPROVER, s.voice_id, "222222")
    assert (r2.session.status, r2.attempts_remaining) == (VoiceStatus.RETRY, 1)
    r3 = svc.complete(a.approval_id, APPROVER, s.voice_id, "333333")
    assert (r3.session.status, r3.attempts_remaining) == (VoiceStatus.FALLBACK_CALLBACK, 0)
    with pytest.raises(VoiceError):
        svc.complete(a.approval_id, APPROVER, s.voice_id, "482913")
    assert not svc.is_tier2_passed(a.approval_id)
    assert ("voice_failed", "Three wrong tries; falls back to call-back") in events.steps


def test_new_code_does_not_reset_wrong_tries(env):
    svc, approvals, _, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "ta").session
    svc.complete(a.approval_id, APPROVER, s.voice_id, "111111")
    svc.complete(a.approval_id, APPROVER, s.voice_id, "222222")
    s2 = svc.start(a.approval_id, APPROVER, "ta")
    assert s2.attempts_remaining == 1
    r = svc.complete(a.approval_id, APPROVER, s2.session.voice_id, "333333")
    assert r.session.status is VoiceStatus.FALLBACK_CALLBACK


def test_new_code_invalidates_old_one(env):
    svc, approvals, _, _ = env
    a = approvals.add()
    old = svc.start(a.approval_id, APPROVER, "en").session
    svc.start(a.approval_id, APPROVER, "en")
    with pytest.raises(VoiceError) as e:
        svc.complete(a.approval_id, APPROVER, old.voice_id, "482913")
    assert e.value.slug == "no-active-code"


def test_too_many_codes_fall_back(env):
    svc, approvals, events, _ = env
    a = approvals.add()
    for _ in range(3):
        svc.start(a.approval_id, APPROVER, "en")
    r = svc.start(a.approval_id, APPROVER, "en")
    assert r.code is None
    assert r.session.status is VoiceStatus.FALLBACK_CALLBACK
    assert events.last["data"]["digits_sha256"] is None


def test_code_bound_to_approval(env):
    svc, approvals, _, _ = env
    a, b = approvals.add(), approvals.add()
    sa = svc.start(a.approval_id, APPROVER, "en")
    sb = svc.start(b.approval_id, APPROVER, "en")
    with pytest.raises(VoiceError):
        svc.complete(b.approval_id, APPROVER, sa.session.voice_id, sa.code)
    r = svc.complete(b.approval_id, APPROVER, sb.session.voice_id, sa.code)
    assert r.session.status is VoiceStatus.RETRY


@pytest.mark.parametrize(
    "tier,verified,slug",
    [(1, True, "tier-too-low"), (2, False, "tier1-not-verified"), (3, False, "tier1-not-verified")],
)
def test_needs_tier1_signature_and_tier2(env, tier, verified, slug):
    svc, approvals, _, _ = env
    a = approvals.add(tier=tier, verified=verified)
    with pytest.raises(VoiceError) as e:
        svc.start(a.approval_id, APPROVER, "en")
    assert e.value.slug == slug


def test_other_approver_gets_not_found(env):
    svc, approvals, _, _ = env
    a = approvals.add()
    with pytest.raises(VoiceError) as e:
        svc.start(a.approval_id, "uid_someone_else", "en")
    assert e.value.status == 404


@pytest.mark.parametrize("digits", ["12345", "1234567", "12a456", "١٢٣٤٥٦"])
def test_rejects_malformed_digits(env, digits):
    svc, approvals, _, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "en").session
    with pytest.raises(VoiceError) as e:
        svc.complete(a.approval_id, APPROVER, s.voice_id, digits)
    assert e.value.slug == "bad-digits"
    assert svc.store.get_by_approval(a.approval_id).wrong_tries == 0


def test_event_envelope_and_no_digits_in_ledger(env):
    svc, approvals, events, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "en").session
    svc.complete(a.approval_id, APPROVER, s.voice_id, "111111")
    topic, env_ = events.published[-1]
    assert topic == EVENT_TOPIC == "approval-voice-checked"
    assert set(env_) == {"event_id", "event_type", "occurred_at", "company_id", "intent_id", "actor", "data"}
    assert env_["event_type"] == EVENT_TYPE
    assert env_["occurred_at"].endswith("+05:30")
    assert env_["actor"] == {"type": "human", "id": APPROVER}
    assert env_["intent_id"] == a.intent_id
    assert "111111" not in str(env_)
    assert env_["data"]["digits_sha256"] == digits_hash(a.approval_id, a.nonce, "111111")
    assert env_["data"]["attempt"] == 1


def test_concurrent_wrong_tries_never_exceed_limit(env):
    svc, approvals, _, _ = env
    a = approvals.add()
    s = svc.start(a.approval_id, APPROVER, "en").session
    errors: list[Exception] = []

    def guess(d: str) -> None:
        try:
            svc.complete(a.approval_id, APPROVER, s.voice_id, d)
        except VoiceError as e:
            errors.append(e)

    threads = [threading.Thread(target=guess, args=(f"{i:06d}",)) for i in range(100, 120)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = svc.store.get_by_approval(a.approval_id)
    assert final.status is VoiceStatus.FALLBACK_CALLBACK
    assert final.wrong_tries == 3
    assert len(errors) == 17


# ---- HTTP layer -------------------------------------------------------------


@pytest.fixture
def client(env):
    svc, approvals, _, _ = env
    app = FastAPI()
    app.include_router(voice_router.router)
    app.dependency_overrides[voice_router.get_voice_service] = lambda: svc
    app.dependency_overrides[voice_router.current_approver_uid] = lambda: APPROVER
    return TestClient(app), approvals


def test_http_start_then_complete(client):
    c, approvals = client
    a = approvals.add()
    r = c.post(f"/v1/approvals/{a.approval_id}/voice", json={"action": "start", "language": "ta"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "482913" and body["attempts_remaining"] == 3 and body["matched"] is False
    assert body["expires_at"].endswith("+05:30")
    r = c.post(
        f"/v1/approvals/{a.approval_id}/voice",
        json={"action": "complete", "voice_id": body["voice_id"], "digits": "482913"},
    )
    assert r.json()["status"] == "passed" and r.json()["matched"] is True
    assert "code" not in r.json()


def test_http_accepts_contract_example_id_shape(client):
    """The contract's ID pattern is ^ap_[A-Za-z0-9]+$, so non-Crockford ids must route."""
    c, _ = client
    r = c.post("/v1/approvals/ap_01JD2XBOSSSCAM0001/voice", json={"action": "start", "language": "en"})
    assert r.status_code == 404  # routed and refused as unknown, not a 422 on the path


def test_http_problem_details(client):
    c, approvals = client
    a = approvals.add(verified=False)
    r = c.post(f"/v1/approvals/{a.approval_id}/voice", json={"action": "start", "language": "en"})
    assert r.status_code == 409
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["type"] == "https://pramaan.example/problems/tier1-not-verified"


def test_http_rejects_bad_language(client):
    c, approvals = client
    a = approvals.add()
    r = c.post(f"/v1/approvals/{a.approval_id}/voice", json={"action": "start", "language": "fr"})
    assert r.status_code == 422
