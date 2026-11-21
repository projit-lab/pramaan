"""Live smoke test of the M2+ engine against a running API in ENV=local.

    ENV=local uvicorn app.main:app --port 8090        (from services/api)
    python scripts/m2plus_smoke.py [base_url]

Time-dependent steps (the batch window, escalation) use the ENV=local job routes
with an explicit time, so the script works at any hour.
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


with httpx.Client(base_url=BASE, timeout=15) as c:
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
        r = c.post("/v1/intents", json=body, headers=user("clerk"))
        assert r.status_code == 201, r.text
        return r.json()

    tree = {n["node_id"]: n for n in c.get("/v1/org/tree", headers=user("finance")).json()["nodes"]}
    check(
        "organisation tree is seeded (upgrade from M2 worked)",
        {"org_acme_group", "org_acme", "org_acme_chennai", "org_acme_ap"} <= set(tree),
    )
    check(
        "AP department inherits the group and company rules",
        tree["org_acme_ap"]["inherited_rule_codes"] == ["very_large", "new_payee_large"],
    )
    levels = [
        a["level_name"] for a in c.get("/v1/approvers", headers=user("finance")).json()["approvers"]
    ]
    check(
        "approver hierarchy has all four levels",
        {"MD", "CFO", "Controller", "AP Manager"} <= set(levels),
    )

    hour = datetime.now(IST).hour
    after_hours = not (9 <= hour < 19)
    small = intent()
    # After hours the outside-working-hours rule makes it tier 1, which is not a
    # hard flag in the plan's list, so a clean tier 1 is batched.
    want = "batch" if after_hours else "auto_release"
    check(
        f"Rs 2 lakh to a known vendor: {want}",
        small["lane"] == want,
        f"{small['lane']} (IST hour {hour})",
    )

    laxmi = intent(payee_vendor_id="vd_sri_laxmi")
    p = c.get(f"/v1/intents/{laxmi['intent_id']}", headers=user("clerk")).json()
    check(
        "look-alike vendor caught by the payee checks",
        laxmi["lane"] == "individual" and p["payee_checks"]["look_alike_of"] == "vd_sri_lakshmi",
        str(p["payee_checks"]["look_alike_score"]),
    )

    boss = intent(
        payee_vendor_id="vd_global_trade", amount_paise="465000000", instruction_channel="chat"
    )
    check(
        "boss scam is tier 2 for the Controller, with the company rule's path",
        boss["tier"] == 2
        and any(
            r["path"] == "Acme Group > Acme Engineering" for r in boss["decision_trace"]["rules"]
        ),
    )
    big = intent(payee_vendor_id="vd_global_trade", amount_paise="1500000000")
    pb = c.get(f"/v1/intents/{big['intent_id']}", headers=user("clerk")).json()
    check(
        "Rs 1.5 crore is tier 3 for the CFO and the MD",
        big["tier"] == 3 and pb["approvers"] == ["cfo@acme.example", "md@acme.example"],
    )

    # Batch lane: a clean tier 1 waits for the next approval window.
    b1 = intent(amount_paise="60000000")
    check("clean tier 1 goes to the batch lane", b1["lane"] == "batch", b1["batch_window_at"] or "")
    at = datetime.fromisoformat(b1["batch_window_at"]) + timedelta(minutes=1)
    made = c.post(
        "/v1/_local/jobs/close-batches", json={"at": at.isoformat()}, headers=user("finance")
    ).json()["batches"]
    check(
        "batch closes at the window for the AP Manager",
        any(m["approver"] == "ap.manager@acme.example" for m in made),
        str(made),
    )
    batches = c.get("/v1/batches?status=pending", headers=user("ap.manager")).json()["batches"]
    check(
        "AP Manager sees the batch with its lines",
        any(b1["intent_id"] in {ln["intent_id"] for ln in b["lines"]} for b in batches),
        f"{len(batches)} batch(es), {sum(b['line_count'] for b in batches)} lines",
    )

    # Escalation: the tier 2 waits on the Controller; four hours later the CFO is asked too.
    later = datetime.now(timezone.utc) + timedelta(hours=4, minutes=1)
    up = c.post(
        "/v1/_local/jobs/escalate", json={"at": later.isoformat()}, headers=user("finance")
    ).json()["escalated"]
    check(
        "an undecided approval escalates upward",
        any(
            e["intent_id"] == boss["intent_id"] and e["approver"] == "cfo@acme.example" for e in up
        ),
        str([(e["approver"]) for e in up]),
    )

    # The tree editor refuses to loosen.
    r = c.put(
        "/v1/org/nodes/org_acme_treasury",
        json={"settings": {"tier1_paise": "60000000"}},
        headers=user("finance"),
    )
    check(
        "loosening Treasury's threshold is refused with the reason",
        r.status_code == 422 and "looser" in r.json()["errors"][0]["detail"],
    )
    r = c.post(
        "/v1/_local/delegations",
        json={"delegate_email": "ap.manager@acme.example"},
        headers=user("cfo"),
    )
    check("delegating to someone more junior is refused", r.status_code == 422)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
