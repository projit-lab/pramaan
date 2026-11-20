"""Tier 2 voice step: one-time code issue and check (M4).

Contract: POST /approvals/{approvalId}/voice in contracts/openapi.yaml, event
approval.voice_checked in contracts/events.md.

Rules:
- Runs only after the Tier 1 signature on the approval has been verified, and
  only at tier 2 and above. It adds a check; it never replaces the signature.
- The code is six digits, bound to the approval and its nonce, valid for two
  minutes and usable once.
- Only an exact match completes Tier 2. Three wrong tries end the voice step
  and fall back to a call-back. The try count belongs to the approval, so a
  fresh code never resets it, and at most three codes are issued.
- Audio is never stored. The ledger keeps only the result and a hash.
- A deliberate confirmation through a second channel, not a voice biometric.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Protocol

from app.domain.ids import new_id

CODE_TTL = timedelta(minutes=2)
MAX_WRONG_TRIES = 3
MAX_CODES_PER_APPROVAL = 3
LANGUAGES = frozenset({"ta", "hi", "en"})
IST = timezone(timedelta(hours=5, minutes=30))

EVENT_TYPE = "approval.voice_checked"
EVENT_TOPIC = "approval-voice-checked"


class VoiceStatus(str, Enum):
    AWAITING_CODE = "awaiting_code"
    PASSED = "passed"
    RETRY = "retry"
    EXPIRED = "expired"
    FALLBACK_CALLBACK = "fallback_callback"


TERMINAL = frozenset({VoiceStatus.PASSED, VoiceStatus.FALLBACK_CALLBACK})


class VoiceError(Exception):
    """Maps to a problem-details response."""

    def __init__(self, status: int, title: str, detail: str, slug: str) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.slug = slug


@dataclass(frozen=True)
class ApprovalView:
    """What the voice step needs to know about an approval."""

    approval_id: str
    intent_id: str
    company_id: str
    nonce: str
    tier: int
    tier1_verified: bool
    approver_uid: str


@dataclass(frozen=True)
class VoiceSession:
    voice_id: str
    approval_id: str
    intent_id: str
    company_id: str
    nonce: str
    language: str
    code_mac: bytes
    expires_at: datetime
    status: VoiceStatus
    wrong_tries: int = 0
    codes_issued: int = 1


@dataclass(frozen=True)
class VoiceResult:
    session: VoiceSession
    code: str | None = None  # only on start

    @property
    def attempts_remaining(self) -> int:
        return max(0, MAX_WRONG_TRIES - self.session.wrong_tries)

    @property
    def matched(self) -> bool:
        return self.session.status is VoiceStatus.PASSED


class ApprovalLookup(Protocol):
    def get(self, approval_id: str) -> ApprovalView | None: ...


class VoiceStore(Protocol):
    """One voice session per approval. `update` must be atomic per approval
    (SELECT ... FOR UPDATE in AlloyDB, or a Firestore transaction)."""

    def get_by_approval(self, approval_id: str) -> VoiceSession | None: ...

    def update(
        self,
        approval_id: str,
        fn: Callable[[VoiceSession | None], VoiceSession],
    ) -> VoiceSession: ...


class VoiceEvents(Protocol):
    def publish(self, topic: str, envelope: dict[str, Any]) -> None: ...
    def step(self, intent_id: str, step: str, detail: str) -> None: ...


def _code_mac(secret: bytes, approval_id: str, nonce: str, voice_id: str, code: str) -> bytes:
    msg = f"{approval_id}|{nonce}|{voice_id}|{code}".encode()
    return hmac.new(secret, msg, hashlib.sha256).digest()


def digits_hash(approval_id: str, nonce: str, digits: str) -> str:
    return hashlib.sha256(f"{approval_id}|{nonce}|{digits}".encode()).hexdigest()


def ist(dt: datetime) -> str:
    return dt.astimezone(IST).isoformat(timespec="seconds")


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass
class VoiceService:
    approvals: ApprovalLookup
    store: VoiceStore
    events: VoiceEvents
    secret: bytes
    now: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))
    code_factory: Callable[[], str] = field(default=_new_code)

    def _approval(self, approval_id: str, caller_uid: str) -> ApprovalView:
        approval = self.approvals.get(approval_id)
        if approval is None or approval.approver_uid != caller_uid:
            # Same answer for "missing" and "not yours", so ids can't be probed.
            raise VoiceError(404, "Approval not found", "No such approval for this approver.", "not-found")
        if approval.tier < 2:
            raise VoiceError(409, "Voice step not required", "This approval is below Tier 2.", "tier-too-low")
        if not approval.tier1_verified:
            raise VoiceError(
                409,
                "Tier 1 signature required first",
                "The voice step runs only after the fingerprint signature is verified.",
                "tier1-not-verified",
            )
        return approval

    # ---- start -----------------------------------------------------------

    def start(self, approval_id: str, caller_uid: str, language: str) -> VoiceResult:
        if language not in LANGUAGES:
            raise VoiceError(422, "Unsupported language", "Language must be ta, hi or en.", "bad-language")
        approval = self._approval(approval_id, caller_uid)
        code = self.code_factory()
        now = self.now()

        def issue(prev: VoiceSession | None) -> VoiceSession:
            if prev is not None and prev.status in TERMINAL:
                raise VoiceError(
                    409,
                    "Voice step already finished",
                    f"The voice step is {prev.status.value}.",
                    "voice-finished",
                )
            if prev is not None and prev.codes_issued >= MAX_CODES_PER_APPROVAL:
                return replace(prev, status=VoiceStatus.FALLBACK_CALLBACK)
            voice_id = new_id("vs")
            return VoiceSession(
                voice_id=voice_id,
                approval_id=approval.approval_id,
                intent_id=approval.intent_id,
                company_id=approval.company_id,
                nonce=approval.nonce,
                language=language,
                code_mac=_code_mac(self.secret, approval.approval_id, approval.nonce, voice_id, code),
                expires_at=now + CODE_TTL,
                status=VoiceStatus.AWAITING_CODE,
                wrong_tries=prev.wrong_tries if prev else 0,  # never reset by a new code
                codes_issued=(prev.codes_issued + 1) if prev else 1,
            )

        session = self.store.update(approval.approval_id, issue)
        if session.status is VoiceStatus.FALLBACK_CALLBACK:
            self._emit(session, caller_uid, "fallback_callback", "", now)
            self.events.step(session.intent_id, "voice_failed", "Too many codes asked for; falls back to call-back")
            return VoiceResult(session)
        self.events.step(session.intent_id, "voice_started", f"Spoken code requested ({language})")
        return VoiceResult(session, code=code)

    # ---- complete ----------------------------------------------------------

    def complete(self, approval_id: str, caller_uid: str, voice_id: str, digits: str) -> VoiceResult:
        if len(digits) != 6 or not digits.isascii() or not digits.isdigit():
            raise VoiceError(422, "Invalid digits", "Send exactly six digits.", "bad-digits")
        approval = self._approval(approval_id, caller_uid)
        now = self.now()
        outcome: dict[str, str] = {}

        def check(prev: VoiceSession | None) -> VoiceSession:
            if prev is None or prev.voice_id != voice_id:
                raise VoiceError(409, "No active code", "Start the voice step to get a code.", "no-active-code")
            if prev.status in TERMINAL:
                raise VoiceError(
                    409, "Voice step already finished", f"The voice step is {prev.status.value}.", "voice-finished"
                )
            if prev.status is VoiceStatus.EXPIRED or now >= prev.expires_at:
                outcome["result"] = "expired"
                return replace(prev, status=VoiceStatus.EXPIRED)
            got = _code_mac(self.secret, prev.approval_id, prev.nonce, prev.voice_id, digits)
            if hmac.compare_digest(prev.code_mac, got):
                outcome["result"] = "passed"
                # Single use: PASSED is terminal, so the code can never be checked again.
                return replace(prev, status=VoiceStatus.PASSED)
            tries = prev.wrong_tries + 1
            if tries >= MAX_WRONG_TRIES:
                outcome["result"] = "fallback_callback"
                return replace(prev, wrong_tries=tries, status=VoiceStatus.FALLBACK_CALLBACK)
            outcome["result"] = "mismatch"
            return replace(prev, wrong_tries=tries, status=VoiceStatus.RETRY)

        session = self.store.update(approval.approval_id, check)
        result = outcome["result"]
        self._emit(session, caller_uid, result, digits, now)
        if result == "passed":
            self.events.step(session.intent_id, "voice_verified", f"Spoken code matched ({session.language})")
        elif result == "fallback_callback":
            self.events.step(session.intent_id, "voice_failed", "Three wrong tries; falls back to call-back")
        elif result == "expired":
            self.events.step(session.intent_id, "voice_failed", "Code expired; the approver can ask for a new one")
        return VoiceResult(session)

    def _emit(self, s: VoiceSession, actor_uid: str, result: str, digits: str, now: datetime) -> None:
        attempt = s.wrong_tries + (1 if result == "passed" else 0)
        self.events.publish(
            EVENT_TOPIC,
            {
                "event_id": new_id("ev"),
                "event_type": EVENT_TYPE,
                "occurred_at": ist(now),
                "company_id": s.company_id,
                "intent_id": s.intent_id,
                "actor": {"type": "human", "id": actor_uid},
                "data": {
                    "approval_id": s.approval_id,
                    "voice_id": s.voice_id,
                    "language": s.language,
                    "result": result,
                    "attempt": attempt,
                    "digits_sha256": digits_hash(s.approval_id, s.nonce, digits) if digits else None,
                },
            },
        )

    def is_tier2_passed(self, approval_id: str) -> bool:
        """For mandate issuance: at tier 2 and above, issue the mandate only when this is true."""
        s = self.store.get_by_approval(approval_id)
        return s is not None and s.status is VoiceStatus.PASSED


class InMemoryVoiceStore:
    """For tests and DEMO_MODE. Production uses AlloyDB with a row lock."""

    def __init__(self) -> None:
        self._rows: dict[str, VoiceSession] = {}
        self._lock = threading.Lock()

    def get_by_approval(self, approval_id: str) -> VoiceSession | None:
        return self._rows.get(approval_id)

    def update(self, approval_id: str, fn: Callable[[VoiceSession | None], VoiceSession]) -> VoiceSession:
        with self._lock:
            new = fn(self._rows.get(approval_id))
            self._rows[approval_id] = new
            return new
