"""Live smoke test of the M2 plumbing against a running API in ENV=local.

    ENV=local uvicorn app.main:app --port 8090        (from services/api)
    python scripts/m2_smoke.py [base_url]

Uses the X-Dev-User header, which the API accepts only when ENV=local.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090"
IST = timezone(timedelta(hours=5, minutes=30))
results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def user(name: str) -> dict[str, str]:
    return {"X-Dev-User": name}


hour = datetime.now(IST).hour
after_hours = not (9 <= hour < 19)
extra = ["outside_working_hours"] if after_hours else []
print(f"IST hour {hour}: outside working hours = {after_hours}\n")

with httpx.Client(base_url=BASE, timeout=10) as c:
    for _ in range(60):
        try:
            c.get("/v1/health")
            break
        except httpx.ConnectError:
            time.sleep(0.5)

    def intent(**kw):
        body = {
            "amount_paise": "20000000",
            "instruction_channel": "portal",
            "initiator": {"type": "human", "id": "clerk@acme.example"},
            "payee_vendor_id": "vd_sri_lakshmi",
            "purpose": "INV-2219",
        }
        body.update(kw)
        return c.post("/v1/intents", json=body, headers=user("clerk"))

    r = intent()
    g = r.json()
    codes = [x["code"] for x in g.get("reasons", [])]
    check(
        "genuine Rs 2 lakh to a known vendor",
        r.status_code == 201 and codes == extra and g["tier"] == (1 if after_hours else 0),
        f"tier {g.get('tier')} {g.get('decision')} {codes}",
    )

    r = intent(
        payee_vendor_id="vd_global_trade",
        amount_paise="465000000",
        instruction_channel="chat",
        instruction_note="MD asked for this urgently and confidentially, do not call",
        purpose="Urgent vendor advance",
    )
    boss = r.json()
    codes = [x["code"] for x in boss["reasons"]]
    check(
        "boss scam Rs 46.5 lakh by chat is held at tier 2",
        boss["tier"] == 2
        and boss["status"] == "held"
        and {"new_payee", "amount_above_25_lakh", "instruction_by_chat"} <= set(codes),
        f"{codes}",
    )

    r = intent(payee_vendor_id="vd_sri_laxmi", amount_paise="120000000", purpose="INV-7731")
    check(
        "look-alike vendor with changed bank is tier 3",
        r.json()["tier"] == 3,
        str(r.json()["tier"]),
    )

    r = intent(amount_paise="1.5")
    check(
        "bad amount is a 422 problem",
        r.status_code == 422 and r.headers["content-type"] == "application/problem+json",
    )

    cfo = c.get("/v1/approvals?status=pending", headers=user("cfo")).json()["approvals"]
    md = c.get("/v1/approvals?status=pending", headers=user("md")).json()["approvals"]
    boss_cfo = next((a for a in cfo if a["intent_id"] == boss["intent_id"]), None)
    check(
        "boss scam waits for the CFO and the MD",
        boss_cfo is not None and any(a["intent_id"] == boss["intent_id"] for a in md),
        f"cfo has {len(cfo)}, md has {len(md)}",
    )
    check(
        "CFO's list is riskiest first",
        [a["tier"] for a in cfo] == sorted([a["tier"] for a in cfo], reverse=True),
    )

    p = c.get(f"/v1/intents/{boss['intent_id']}", headers=user("clerk")).json()
    check(
        "GET intent shows the held payment",
        p["status"] == "held"
        and p["payee"]["account_last4"] == "9032"
        and p["amount_paise"] == "465000000",
    )

    r = c.post(
        f"/v1/_local/approvals/{boss_cfo['approval_id']}/block",
        json={"decision": "report_fraud"},
        headers=user("cfo"),
    )
    check(
        "CFO reports it as fraud",
        r.status_code == 200 and r.json()["status"] == "blocked",
        r.text[:120],
    )
    p = c.get(f"/v1/intents/{boss['intent_id']}", headers=user("clerk")).json()
    check("payment is now blocked", p["status"] == "blocked", p["status"])
    md_after = c.get("/v1/approvals?status=pending", headers=user("md")).json()["approvals"]
    check(
        "MD's approval closed with it", all(a["intent_id"] != boss["intent_id"] for a in md_after)
    )
    r = c.post(
        f"/v1/_local/approvals/{boss_cfo['approval_id']}/block",
        json={"decision": "decline"},
        headers=user("cfo"),
    )
    check("deciding twice is refused", r.status_code == 409, str(r.status_code))

    v = c.get("/v1/vendors", headers=user("clerk")).json()["vendors"]
    laxmi = next(x for x in v if x["vendor_id"] == "vd_sri_laxmi")
    check(
        "vendor master: 4 vendors, look-alike shows bank change",
        len(v) == 4 and laxmi["bank_changed_at"] is not None,
    )
    pol = c.get("/v1/policies", headers=user("clerk")).json()
    check("policy 2026.11.1 is served", pol["version"] == "2026.11.1")
    check(
        "unknown mandate is 404 without sign-in", c.get("/v1/mandates/pm_NOPE").status_code == 404
    )
    k = c.get("/v1/keys/countersign")
    check(
        "countersign key is served (Prajit's)",
        k.status_code == 200 and "BEGIN PUBLIC KEY" in k.json()["pem"],
    )
    check("no sign-in, no intents", c.post("/v1/intents", json={}).status_code == 401)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
