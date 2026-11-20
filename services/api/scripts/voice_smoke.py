"""Live smoke test of the Tier 2 voice step against the API in DEMO_MODE.

    DEMO_MODE=true uvicorn main:create_app --factory --port 8765     (from services/api)
    python scripts/voice_smoke.py [base_url]
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def voice(c: httpx.Client, ap: str, body: dict, uid: str = "uid_cfo") -> httpx.Response:
    return c.post(f"/v1/approvals/{ap}/voice", json=body, headers={"X-Demo-Uid": uid})


with httpx.Client(base_url=BASE, timeout=5) as c:
    for _ in range(40):
        try:
            c.get("/healthz")
            break
        except httpx.ConnectError:
            time.sleep(0.25)
    ids = c.post("/_demo/voice/reset").json()

    r = voice(c, ids["tier1"], {"action": "start", "language": "en"})
    check("tier 1 refused", r.status_code == 409 and r.json()["type"].endswith("/tier-too-low"), str(r.status_code))
    r = voice(c, ids["tier2_unsigned"], {"action": "start", "language": "ta"})
    check("before fingerprint refused", r.status_code == 409 and r.json()["type"].endswith("/tier1-not-verified"))
    r = voice(c, ids["tier2"], {"action": "start", "language": "ta"}, uid="uid_attacker")
    check("other user gets 404", r.status_code == 404, str(r.status_code))
    r = voice(c, ids["tier2"], {"action": "start", "language": "fr"})
    check("unsupported language 422", r.status_code == 422, str(r.status_code))

    s = voice(c, ids["tier2"], {"action": "start", "language": "ta"}).json()
    check(
        "start returns code",
        len(s.get("code", "")) == 6 and s["attempts_remaining"] == 3 and s["matched"] is False
        and s["expires_at"].endswith("+05:30"),
    )
    code, vid = s["code"], s["voice_id"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    r = voice(c, ids["tier2"], {"action": "complete", "voice_id": vid, "digits": "12a456"})
    check("malformed digits 422", r.status_code == 422, str(r.status_code))
    r = voice(c, ids["tier2"], {"action": "complete", "voice_id": vid, "digits": wrong}).json()
    check("wrong code -> retry", r["status"] == "retry" and r["attempts_remaining"] == 2, r["status"])
    r = voice(c, ids["tier2"], {"action": "complete", "voice_id": vid, "digits": code}).json()
    check("right code -> passed", r["status"] == "passed" and r["matched"] is True and "code" not in r, r["status"])
    r = voice(c, ids["tier2"], {"action": "complete", "voice_id": vid, "digits": code})
    check("code can't be reused", r.status_code == 409, str(r.status_code))
    r = voice(c, ids["tier2"], {"action": "start", "language": "ta"})
    check("can't restart after pass", r.status_code == 409, str(r.status_code))

    ev = c.get("/_demo/voice/events").json()
    pub = [e for e in ev["published"] if e["event_type"] == "approval.voice_checked"]
    leaked = any(code in str(e) or wrong in str(e) for e in pub)
    check(
        "events: envelope, hashes only",
        len(pub) == 2 and not leaked and all(e["topic"] == "approval-voice-checked" for e in pub)
        and all(len(e["data"]["digits_sha256"]) == 64 for e in pub),
    )
    check("firestore steps", [x["step"] for x in ev["steps"]] == ["voice_started", "voice_verified"])
    spec = c.get("/openapi.json").json()
    check("served spec has only contract paths", list(spec["paths"]) == ["/v1/approvals/{approvalId}/voice"])
    c.post("/_demo/voice/reset")

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
