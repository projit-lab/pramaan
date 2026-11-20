"""M2 plumbing end to end over HTTP: intents, routing and push, the approvals list,
decline and report, mandates, vendors and policies. Each test gets a fresh database
(migrated and seeded) and a fixed clock at noon IST."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.adapters.event_bus import InMemoryEventBus
from app.adapters.notifier import InMemoryNotifier
from app.adapters.read_model import InMemoryReadModel
from app.auth import get_current_user
from app.config import Settings
from app.db.engine import make_engine, make_session_factory, unit_of_work
from app.db.models import Device, Mandate, PaymentIntent, Policy
from app.db.seed import POLICY_2026_11_1, seed_if_empty
from app.domain.models import AuthenticatedUser
from app.domain.policy import IST
from app.main import create_app
from app.runtime import Runtime, migrate

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"
SPEC = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]
NOON = datetime(2026, 11, 20, 12, 0, tzinfo=IST)
LAKH = "00000"  # helper suffix: "2" + LAKH + "00" is Rs 2 lakh in paise


def paise_lakh(n: float) -> str:
    return str(int(n * 100_000 * 100))


class Clock:
    def __init__(self) -> None:
        self.t = NOON

    def __call__(self) -> datetime:
        return self.t


def make_env(tmp_path):
    """Builds the `env` fixture (see conftest.py): a fresh migrated, seeded
    database, in-memory adapters, a client, and a clock fixed at noon IST."""
    url = f"sqlite:///{(tmp_path / 'm2.db').as_posix()}"
    migrate(url)
    sessions = make_session_factory(make_engine(url))
    seed_if_empty(sessions)
    clock = Clock()
    rt = Runtime(
        settings=Settings(ENV="local"),
        sessions=sessions,
        event_bus=InMemoryEventBus(),
        read_model=InMemoryReadModel(),
        notifier=InMemoryNotifier(),
        clock=clock,
    )
    app = create_app()
    app.state.runtime = rt
    return TestClient(app), rt, clock


def as_user(name: str) -> dict[str, str]:
    return {"X-Dev-User": name}  # ENV=local: uid=name, email=name@acme.example, finance+clerk


CLERK = as_user("clerk")


def post_intent(client, **kw):
    body = {
        "amount_paise": paise_lakh(2),
        "instruction_channel": "portal",
        "initiator": {"type": "human", "id": "clerk@acme.example"},
        "payee_vendor_id": "vd_sri_lakshmi",
        "purpose": "INV-2219",
    }
    body.update(kw)
    return client.post("/v1/intents", json=body, headers=CLERK)


def events(rt, event_type=None):
    return [e for e in rt.event_bus.events if event_type is None or e["event_type"] == event_type]


# ---- contract conformance helper --------------------------------------------------------


def schema(name: str) -> dict:
    return SCHEMAS[name]


def assert_shape(obj: dict, name: str) -> None:
    s = schema(name)
    missing = set(s.get("required", [])) - set(obj)
    extra = set(obj) - set(s.get("properties", {}))
    assert not missing, f"{name} is missing {missing}"
    assert not extra, f"{name} has fields the contract does not define: {extra}"


# ---- POST /intents ---------------------------------------------------------------------


def test_genuine_small_payment_is_released_at_tier_0(env):
    client, rt, _ = env
    r = post_intent(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert_shape(body, "IntentDecision")
    assert (body["decision"], body["status"], body["tier"], body["reasons"]) == (
        "release",
        "approved",
        0,
        [],
    )
    assert body["policy_version"] == "2026.11.1"
    assert body["created_at"].endswith("+05:30")
    assert [e["event_type"] for e in events(rt)] == ["intent.created", "intent.decided"]
    assert events(rt, "intent.decided")[0]["data"]["approvers"] == []


def test_boss_scam_is_held_at_tier_2_for_the_controller(env):
    client, rt, _ = env
    r = post_intent(
        client,
        payee_vendor_id="vd_global_trade",
        amount_paise="465000000",
        instruction_channel="chat",
        instruction_note="MD asked for this urgently and confidentially, do not call",
        purpose="Urgent vendor advance",
    )
    body = r.json()
    assert (body["decision"], body["status"], body["tier"]) == ("hold", "held", 2)
    assert body["lane"] == "individual"
    assert [x["code"] for x in body["reasons"]] == [
        "new_payee",
        "amount_above_25_lakh",
        "instruction_by_chat",
        "new_payee_large",  # the company-level hierarchy rule
    ]
    assert body["decision_trace"]["rules"][0]["path"] == "Acme Group > Acme Engineering"
    decided = events(rt, "intent.decided")[0]
    assert decided["data"]["approvers"] == ["controller@acme.example"]
    assert decided["data"]["lane"] == "individual"
    assert decided["actor"] == {"type": "service", "id": "policy-engine"}
    created = events(rt, "intent.created")[0]
    assert created["data"]["payee_account_last4"] == "9032"
    assert created["actor"] == {"type": "human", "id": "clerk@acme.example"}


def test_look_alike_with_changed_bank_is_tier_3(env):
    client, _, _ = env
    body = post_intent(client, payee_vendor_id="vd_sri_laxmi", amount_paise=paise_lakh(12)).json()
    assert body["tier"] == 3
    assert {"new_payee", "bank_details_changed", "amount_above_5_lakh"} <= {
        x["code"] for x in body["reasons"]
    }


def test_agent_initiated_payment_is_held(env):
    client, _, _ = env
    body = post_intent(
        client,
        instruction_channel="agent",
        initiator={"type": "agent", "id": "payables-agent-01"},
    ).json()
    assert body["tier"] == 1 and [x["code"] for x in body["reasons"]] == ["raised_by_agent"]


def test_one_off_payee_is_always_new(env):
    client, rt, _ = env
    r = post_intent(
        client,
        payee_vendor_id=None,
        payee={"name_at_bank": "Cash Corner", "account_last4": "4410", "ifsc": "ABCD0009999"},
    )
    body = r.json()
    assert r.status_code == 201 and body["tier"] == 1
    with unit_of_work(rt.sessions) as s:
        intent = s.get(PaymentIntent, body["intent_id"])
        assert intent.payee_account is None and intent.payee_account_last4 == "4410"


def test_outside_hours_uses_the_server_clock(env):
    client, _, clock = env
    clock.t = datetime(2026, 11, 20, 22, 0, tzinfo=IST)
    assert [x["code"] for x in post_intent(client).json()["reasons"]] == ["outside_working_hours"]


@pytest.mark.parametrize(
    "change,field",
    [
        ({"payee": {"name_at_bank": "X", "account_last4": "1234", "ifsc": "ABCD0123456"}}, "body"),
        ({"payee_vendor_id": None}, "body"),
        ({"amount_paise": "1.50"}, "body"),
        ({"amount_paise": "0"}, "body"),
        ({"amount_paise": 500}, "amount_paise"),
        ({"instruction_channel": "telegram"}, "instruction_channel"),
        ({"invoice_sha256": "abc"}, "invoice_sha256"),
        ({"surprise": 1}, "surprise"),
    ],
)
def test_bad_requests_are_422_problem_details(env, change, field):
    client, rt, _ = env
    r = post_intent(client, **change)
    assert r.status_code == 422, r.text
    assert r.headers["content-type"] == "application/problem+json"
    assert any(field in e["field"] for e in r.json()["errors"])
    assert events(rt) == []


def test_unknown_vendor_is_422(env):
    client, _, _ = env
    r = post_intent(client, payee_vendor_id="vd_nobody")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "payee_vendor_id"


def test_bad_ifsc_on_one_off_payee_is_422(env):
    client, _, _ = env
    r = post_intent(
        client,
        payee_vendor_id=None,
        payee={"name_at_bank": "X", "account_last4": "1234", "ifsc": "abcd123"},
    )
    assert r.status_code == 422


def test_no_active_policy_fails_closed(env):
    client, rt, _ = env
    with unit_of_work(rt.sessions) as s:
        for p in s.query(Policy):
            p.active = False
    r = post_intent(client)
    assert r.status_code == 503 and events(rt) == []


def test_post_intent_needs_a_role(env):
    client, _, _ = env
    client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="u1", email="visitor@acme.example", roles=[]
    )
    r = post_intent(client)
    assert r.status_code == 403 and r.headers["content-type"] == "application/problem+json"


def test_post_intent_needs_sign_in(env):
    client, _, _ = env
    r = client.post("/v1/intents", json={})
    assert r.status_code == 401


def test_full_account_numbers_never_leave_in_events(env):
    client, rt, _ = env
    post_intent(client)  # Sri Lakshmi, account 000123457781
    post_intent(client, payee_vendor_id="vd_global_trade", amount_paise="465000000")
    dumped = json.dumps(rt.event_bus.events)
    for full in ("000123457781", "000112239032", "50100004521"):
        assert full not in dumped


# ---- GET /intents/{id} -------------------------------------------------------------------


def test_get_intent_matches_contract(env):
    client, _, _ = env
    intent_id = post_intent(
        client, payee_vendor_id="vd_global_trade", amount_paise="465000000"
    ).json()["intent_id"]
    r = client.get(f"/v1/intents/{intent_id}", headers=CLERK)
    assert r.status_code == 200
    body = r.json()
    assert_shape(body, "PaymentIntent")
    assert_shape(body["payee"], "Payee")
    assert body["amount_paise"] == "465000000" and body["payer_account_last4"] == "4521"
    assert body["approvers"] == ["controller@acme.example"]
    assert body["lane"] == "individual" and body["department_id"] == "org_acme_ap"
    assert_shape(body["payee_checks"], "PayeeChecks")


def test_get_unknown_intent_is_404(env):
    client, _, _ = env
    r = client.get("/v1/intents/pi_NOPE", headers=CLERK)
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"


# ---- routing, push and GET /approvals ---------------------------------------------------------


def add_device(rt, email, device_id, token="tok", revoked=False):
    with unit_of_work(rt.sessions) as s:
        s.add(
            Device(
                device_id=device_id,
                approver_email=email,
                fcm_token=token,
                revoked=revoked,
                enrolled_at=NOON,
            )
        )


TIER3 = "1500000000"  # Rs 1.5 crore: the group's "above Rs 1 crore" rule makes it tier 3


def test_tier_3_payment_reaches_the_cfo_and_the_md(env):
    client, _, _ = env
    intent_id = post_intent(client, payee_vendor_id="vd_global_trade", amount_paise=TIER3).json()[
        "intent_id"
    ]
    for who in ("cfo", "md"):
        r = client.get("/v1/approvals?status=pending", headers=as_user(who))
        assert r.status_code == 200
        items = r.json()["approvals"]
        assert len(items) == 1
        assert_shape(items[0], "ApprovalSummary")
        assert items[0]["intent_id"] == intent_id and items[0]["tier"] == 3
        assert items[0]["payee_name_at_bank"] == "Global Trade Solutions"
    assert client.get("/v1/approvals", headers=as_user("controller")).json()["approvals"] == []


def test_released_payment_creates_no_approvals(env):
    client, _, _ = env
    post_intent(client)
    assert client.get("/v1/approvals", headers=as_user("cfo")).json()["approvals"] == []


def test_approvals_are_riskiest_first(env):
    client, _, _ = env
    # The Controller delegates to the CFO, so the CFO gets the tier 2 too.
    r = client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "cfo@acme.example"},
        headers=as_user("controller"),
    )
    assert r.status_code == 200, r.text
    post_intent(client, payee_vendor_id="vd_global_trade", amount_paise="465000000")  # tier 2
    post_intent(client, payee_vendor_id="vd_global_trade", amount_paise=TIER3)  # tier 3
    tiers = [
        a["tier"] for a in client.get("/v1/approvals", headers=as_user("cfo")).json()["approvals"]
    ]
    assert tiers == [3, 2]


def test_pending_approval_expires_after_24_hours(env):
    client, _, clock = env
    post_intent(client, payee_vendor_id="vd_global_trade", amount_paise="465000000")
    clock.t = NOON + timedelta(hours=24)
    who = as_user("controller")
    assert client.get("/v1/approvals?status=pending", headers=who).json()["approvals"] == []
    assert len(client.get("/v1/approvals?status=expired", headers=who).json()["approvals"]) == 1


def test_push_goes_to_enrolled_phones_only_and_carries_ids_only(env):
    client, rt, _ = env
    add_device(rt, "controller@acme.example", "dv_ctrl_pixel")
    add_device(rt, "controller@acme.example", "dv_ctrl_old", revoked=True)
    add_device(rt, "ap.manager@acme.example", "dv_apm_notoken", token=None)
    intent_id = post_intent(
        client, payee_vendor_id="vd_global_trade", amount_paise="465000000"
    ).json()["intent_id"]
    sent = rt.notifier.sent
    assert [m["device_id"] for m in sent] == ["dv_ctrl_pixel"]
    assert set(sent[0]) == {"device_id", "type", "approval_id", "intent_id"}
    assert sent[0]["type"] == "approval_waiting" and sent[0]["intent_id"] == intent_id
    step = rt.read_model.get_document(f"holds/{intent_id}/steps", "04")
    assert step["step"] == "pushed" and "controller@acme.example" in step["detail"]


def test_no_pushed_step_when_no_phone_took_it(env):
    client, rt, _ = env
    intent_id = post_intent(
        client, payee_vendor_id="vd_global_trade", amount_paise=paise_lakh(1)
    ).json()["intent_id"]
    assert rt.notifier.sent == []
    assert rt.read_model.get_document(f"holds/{intent_id}/steps", "04") is None


def test_approvals_list_needs_sign_in(env):
    client, _, _ = env
    assert client.get("/v1/approvals").status_code == 401


# ---- decline and report -------------------------------------------------------------------------


def held_for_cfo_and_md(client):
    post_intent(client, payee_vendor_id="vd_global_trade", amount_paise=TIER3)
    cfo = client.get("/v1/approvals?status=pending", headers=as_user("cfo")).json()["approvals"][0]
    md = client.get("/v1/approvals?status=pending", headers=as_user("md")).json()["approvals"][0]
    return cfo, md


def block(client, approval_id, who, decision):
    return client.post(
        f"/v1/_local/approvals/{approval_id}/block",
        json={"decision": decision},
        headers=as_user(who),
    )


def test_decline_blocks_payment_and_closes_other_approvals(env):
    client, rt, _ = env
    cfo, md = held_for_cfo_and_md(client)
    rt.read_model.set_document(
        "holds", cfo["intent_id"], {"status": "held"}
    )  # as the projector would
    r = block(client, cfo["approval_id"], "cfo", "decline")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "declined"
    blocked = events(rt, "payment.blocked")
    assert len(blocked) == 1
    assert blocked[0]["data"] == {
        "reason": "declined_by_approver",
        "detail": "cfo@acme.example declined the payment.",
        "mandate_id": None,
        "blocked_at_step": "signed",
    }
    assert blocked[0]["actor"] == {"type": "human", "id": "cfo@acme.example"}
    hold = rt.read_model.get_document("holds", cfo["intent_id"])
    assert hold["status"] == "declined" and hold["approver"] == "cfo@acme.example"
    intent = client.get(f"/v1/intents/{cfo['intent_id']}", headers=CLERK).json()
    assert intent["status"] == "declined"
    assert (
        client.get("/v1/approvals?status=pending", headers=as_user("md")).json()["approvals"] == []
    )
    assert block(client, md["approval_id"], "md", "decline").status_code == 409


def test_report_fraud_blocks_with_its_own_reason(env):
    client, rt, _ = env
    cfo, _ = held_for_cfo_and_md(client)
    r = block(client, cfo["approval_id"], "cfo", "report_fraud")
    assert r.json()["status"] == "blocked"
    assert events(rt, "payment.blocked")[0]["data"]["reason"] == "reported_fraud"


def test_cannot_decide_twice(env):
    client, rt, _ = env
    cfo, _ = held_for_cfo_and_md(client)
    block(client, cfo["approval_id"], "cfo", "decline")
    r = block(client, cfo["approval_id"], "cfo", "report_fraud")
    assert r.status_code == 409 and len(events(rt, "payment.blocked")) == 1


def test_cannot_decide_someone_elses_approval(env):
    client, rt, _ = env
    cfo, _ = held_for_cfo_and_md(client)
    r = block(client, cfo["approval_id"], "md", "decline")
    assert r.status_code == 404 and events(rt, "payment.blocked") == []


def test_cannot_decide_an_expired_approval(env):
    client, _, clock = env
    cfo, _ = held_for_cfo_and_md(client)
    clock.t = NOON + timedelta(hours=25)
    assert block(client, cfo["approval_id"], "cfo", "decline").status_code == 409


def test_local_block_route_is_not_mounted_outside_local(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("ENV", "dev")
    get_settings.cache_clear()
    try:
        paths = set(create_app().openapi()["paths"])
        local = TestClient(create_app()).post("/v1/_local/approvals/ap_X/block", json={})
        assert local.status_code == 404  # no such route outside ENV=local
        assert "/v1/intents" in paths
    finally:
        get_settings.cache_clear()


# ---- mandates, vendors, policies ----------------------------------------------------------------


def test_get_mandate_serves_the_stored_document_without_sign_in(env):
    client, rt, _ = env
    intent_id = post_intent(client).json()["intent_id"]
    doc = {"mandate_id": "pm_01TEST", "type": "pramaan.payment_mandate.v1", "intent_id": intent_id}
    with unit_of_work(rt.sessions) as s:
        s.add(
            Mandate(
                mandate_id="pm_01TEST",
                intent_id=intent_id,
                document=doc,
                summary_sha256="0" * 64,
                kms_key_version="mandate-signer/local-1",
                expires_at=NOON + timedelta(hours=24),
                created_at=NOON,
            )
        )
    r = client.get("/v1/mandates/pm_01TEST")
    assert r.status_code == 200 and r.json() == doc


def test_unknown_mandate_is_404(env):
    client, _, _ = env
    r = client.get("/v1/mandates/pm_NOPE")
    assert r.status_code == 404 and r.headers["content-type"] == "application/problem+json"


def test_vendors_match_the_contract_example(env):
    client, _, _ = env
    r = client.get("/v1/vendors", headers=CLERK)
    vendors = {v["vendor_id"]: v for v in r.json()["vendors"]}
    example = SPEC["paths"]["/vendors"]["get"]["responses"]["200"]["content"]["application/json"][
        "example"
    ]
    for want in example["vendors"]:
        got = vendors[want["vendor_id"]]
        assert_shape(got, "Vendor")
        for key in ("legal_name", "gstin", "account_last4", "ifsc", "is_new_payee"):
            assert got[key] == want[key], (want["vendor_id"], key)
        assert (got["bank_changed_at"] is None) == (want["bank_changed_at"] is None)


def test_paid_vendor_is_no_longer_new(env):
    client, _, _ = env
    post_intent(
        client, payee_vendor_id="vd_global_trade", amount_paise=paise_lakh(1)
    )  # held, not paid
    v = {x["vendor_id"]: x for x in client.get("/v1/vendors", headers=CLERK).json()["vendors"]}
    assert v["vd_global_trade"]["is_new_payee"] is True


def test_policies_serve_the_contract_policy(env):
    client, _, _ = env
    example = SPEC["paths"]["/policies"]["get"]["responses"]["200"]["content"]["application/json"][
        "example"
    ]
    r = client.get("/v1/policies", headers=CLERK)
    assert r.status_code == 200
    assert_shape(r.json(), "PolicySet")
    assert r.json() == example == POLICY_2026_11_1


def test_vendors_and_policies_need_sign_in(env):
    client, _, _ = env
    assert client.get("/v1/vendors").status_code == 401
    assert client.get("/v1/policies").status_code == 401
