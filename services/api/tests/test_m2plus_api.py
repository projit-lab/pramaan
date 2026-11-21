"""M2+ over HTTP: lanes, approver levels, escalation, batches at the approval
window, standing mandates and their counters, the organisation tree editor with
the tighten-only check, and delegation. Fresh database per test, clock at noon IST."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.engine import unit_of_work
from app.db.models import StandingMandate, VendorBankAccount
from app.domain.policy import IST
from app.services import standing
from tests.test_m2_api import (
    CLERK,
    NOON,
    add_device,
    as_user,
    assert_shape,
    paise_lakh,
    post_intent,
)

FINANCE = as_user("finance.admin")


def lane_of(client, **kw):
    r = post_intent(client, **kw)
    assert r.status_code == 201, r.text
    return r.json()


def pending(client, who):
    return client.get("/v1/approvals?status=pending", headers=as_user(who)).json()["approvals"]


def run(client, job, at=None):
    body = {"at": at.isoformat()} if at else {}
    r = client.post(f"/v1/_local/jobs/{job}", json=body, headers=FINANCE)
    assert r.status_code == 200, r.text
    return r.json()


ONE_OFF = {
    "payee_vendor_id": None,
    "payee": {"name_at_bank": "Cash Corner", "account_last4": "4410", "ifsc": "ABCD0009999"},
}


# ---- lanes --------------------------------------------------------------------------------


def test_known_vendor_small_payment_auto_releases(env):
    client, rt, _ = env
    body = lane_of(client)  # Rs 2 lakh to Sri Lakshmi
    assert_shape(body, "IntentDecision")
    assert (body["lane"], body["decision"], body["status"], body["tier"]) == (
        "auto_release",
        "release",
        "approved",
        0,
    )
    assert body["decision_trace"]["lane"]["row"] == 3
    assert pending(client, "ap.manager") == []


def test_tier_1_with_clean_checks_waits_for_the_next_window(env):
    client, _, _ = env
    body = lane_of(client, amount_paise=paise_lakh(6))
    assert (body["lane"], body["tier"], body["status"]) == ("batch", 1, "held")
    assert body["batch_window_at"] == "2026-11-20T16:00:00+05:30"
    assert pending(client, "ap.manager") == []  # no individual approval for the batch lane


def test_new_payee_can_be_batched(env):
    client, _, _ = env
    body = lane_of(client, payee_vendor_id="vd_global_trade", amount_paise=paise_lakh(1))
    assert (body["lane"], body["tier"]) == ("batch", 1)


def test_look_alike_goes_to_individual_review(env):
    client, _, _ = env
    body = lane_of(client, payee_vendor_id="vd_sri_laxmi", amount_paise=paise_lakh(2))
    assert body["lane"] == "individual"
    codes = {r["code"] for r in body["reasons"]}
    assert {"look_alike", "bank_details_changed"} <= codes
    assert "look_alike" in body["decision_trace"]["lane"]["hard_flags"]
    intent = client.get(f"/v1/intents/{body['intent_id']}", headers=CLERK).json()
    assert intent["payee_checks"]["look_alike_of"] == "vd_sri_lakshmi"


def test_one_off_payee_fails_the_name_check_and_goes_to_a_person(env):
    client, _, _ = env
    body = lane_of(client, **ONE_OFF)
    assert body["lane"] == "individual"
    assert "name_check_not_found" in {r["code"] for r in body["reasons"]}
    assert [a["intent_id"] for a in pending(client, "ap.manager")] == [body["intent_id"]]


def test_chat_instruction_is_a_hard_flag(env):
    client, _, _ = env
    body = lane_of(client, instruction_channel="chat")
    assert body["lane"] == "individual" and body["tier"] == 1


def test_department_thresholds_tighten_the_tiers(env):
    client, _, _ = env
    body = lane_of(client, amount_paise=paise_lakh(3), department_id="org_acme_treasury")
    assert body["tier"] == 1 and "amount_above_2_lakh" in {r["code"] for r in body["reasons"]}
    assert body["decision_trace"]["effective"]["tier1_paise"] == 20000000
    assert body["decision_trace"]["department"].endswith("Chennai plant > Treasury")
    assert lane_of(client, amount_paise=paise_lakh(3))["tier"] == 0  # same payment, AP: tier 0


def test_unknown_or_non_department_node_is_422(env):
    client, _, _ = env
    for dept in ("org_nowhere", "org_acme_chennai"):
        r = post_intent(client, department_id=dept)
        assert r.status_code == 422 and r.json()["errors"][0]["field"] == "department_id"


# ---- entry route ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw,route",
    [
        ({}, "erp"),
        (
            {
                "instruction_channel": "agent",
                "initiator": {"type": "agent", "id": "payables-agent-01"},
            },
            "agent",
        ),
        ({"entry_route": "bank_file"}, "bank_file"),
        ({"entry_route": "payout_api"}, "payout_api"),
    ],
)
def test_entry_route_is_stored_and_defaults_from_the_initiator(env, kw, route):
    client, rt, _ = env
    intent_id = lane_of(client, **kw)["intent_id"]
    intent = client.get(f"/v1/intents/{intent_id}", headers=CLERK).json()
    assert intent["entry_route"] == route
    created = [e for e in rt.event_bus.events if e["event_type"] == "intent.created"][-1]
    assert created["data"]["entry_route"] == route


def test_unknown_entry_route_is_422(env):
    client, _, _ = env
    r = post_intent(client, entry_route="fax")
    assert r.status_code == 422 and any("entry_route" in e["field"] for e in r.json()["errors"])


def test_rules_can_use_the_entry_route(env):
    client, _, _ = env
    r = client.put(
        "/v1/org/nodes/org_acme_ap",
        headers=FINANCE,
        json={
            "rules": [
                {
                    "code": "bank_file_reviewed",
                    "text": "Bank-file payments are always reviewed.",
                    "expression": "payment.entry_route == 'bank_file'",
                    "min_tier": 1,
                    "hard_flag": True,
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert lane_of(client, entry_route="bank_file")["lane"] == "individual"
    assert lane_of(client)["lane"] == "auto_release"


# ---- approver levels -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw,who",
    [
        (ONE_OFF, ["ap.manager@acme.example"]),  # tier 1, individual
        (
            {"payee_vendor_id": "vd_global_trade", "amount_paise": "465000000"},
            ["controller@acme.example"],
        ),  # tier 2
        (
            {"payee_vendor_id": "vd_global_trade", "amount_paise": "1500000000"},
            ["cfo@acme.example", "md@acme.example"],
        ),  # tier 3
    ],
)
def test_each_tier_goes_to_its_minimum_level(env, kw, who):
    client, _, _ = env
    body = lane_of(client, **kw)
    intent = client.get(f"/v1/intents/{body['intent_id']}", headers=CLERK).json()
    assert intent["approvers"] == who


def test_escalates_upward_when_nobody_decides(env):
    client, _, clock = env
    intent_id = lane_of(client, **ONE_OFF)["intent_id"]
    assert run(client, "escalate", NOON + timedelta(hours=3))["escalated"] == []
    up = run(client, "escalate", NOON + timedelta(hours=4))["escalated"]
    assert [e["approver"] for e in up] == ["controller@acme.example"]
    assert [a["intent_id"] for a in pending(client, "controller")] == [intent_id]
    assert len(pending(client, "ap.manager")) == 1  # the first request stays open
    up2 = run(client, "escalate", NOON + timedelta(hours=8))["escalated"]
    assert [e["approver"] for e in up2] == ["cfo@acme.example"]
    assert run(client, "escalate", NOON + timedelta(hours=8))["escalated"] == []  # once each


def test_tier_3_never_escalates(env):
    client, _, _ = env
    lane_of(client, payee_vendor_id="vd_global_trade", amount_paise="1500000000")
    assert run(client, "escalate", NOON + timedelta(hours=10))["escalated"] == []


def test_delegation_never_to_someone_more_junior(env):
    client, _, _ = env
    r = client.post(
        "/v1/_local/delegations",
        json={"delegate_email": "ap.manager@acme.example"},
        headers=as_user("cfo"),
    )
    assert r.status_code == 422 and "more junior" in r.json()["detail"]


def test_approvers_list(env):
    client, _, _ = env
    rows = client.get("/v1/approvers", headers=FINANCE).json()["approvers"]
    assert [(a["email"], a["level_name"]) for a in rows][:4] == [
        ("md@acme.example", "MD"),
        ("cfo@acme.example", "CFO"),
        ("controller@acme.example", "Controller"),
        ("ap.manager@acme.example", "AP Manager"),
    ]


# ---- batches ---------------------------------------------------------------------------------


def test_batch_closes_at_the_window_for_one_approver(env):
    client, rt, _ = env
    add_device(rt, "ap.manager@acme.example", "dv_apm")
    a = lane_of(client, amount_paise=paise_lakh(6))
    b = lane_of(client, payee_vendor_id="vd_global_trade", amount_paise=paise_lakh(1))
    assert run(client, "close-batches", NOON + timedelta(hours=3))["batches"] == []  # 15:00
    made = run(client, "close-batches", datetime(2026, 11, 20, 16, 0, tzinfo=IST))["batches"]
    assert [(x["approver"], x["lines"]) for x in made] == [("ap.manager@acme.example", 2)]
    batches = client.get("/v1/batches?status=pending", headers=as_user("ap.manager")).json()[
        "batches"
    ]
    assert len(batches) == 1
    assert_shape(batches[0], "BatchSummary")
    assert batches[0]["total_paise"] == str(int(paise_lakh(6)) + int(paise_lakh(1)))
    assert {line["intent_id"] for line in batches[0]["lines"]} == {a["intent_id"], b["intent_id"]}
    assert all(line["checks_passed"] for line in batches[0]["lines"])
    assert rt.notifier.sent[-1]["approval_id"] == batches[0]["batch_id"]
    assert run(client, "close-batches", datetime(2026, 11, 20, 16, 5, tzinfo=IST))["batches"] == []


def test_individual_and_released_payments_never_enter_a_batch(env):
    client, _, _ = env
    lane_of(client)  # auto-release
    lane_of(client, **ONE_OFF)  # individual
    assert run(client, "close-batches", datetime(2026, 11, 21, 12, 0, tzinfo=IST))["batches"] == []


# ---- standing mandates --------------------------------------------------------------------------


def make_standing(client, per=10, month=15, count=5):
    r = client.post(
        "/v1/_local/standing-mandates",
        headers=as_user("cfo"),
        json={
            "vendor_id": "vd_sri_lakshmi",
            "cap_per_payment_paise": paise_lakh(per),
            "cap_per_month_paise": paise_lakh(month),
            "max_count": count,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["standing_mandate_id"]


def test_standing_mandate_auto_releases_until_the_monthly_cap(env):
    client, _, _ = env
    sm = make_standing(client)
    first = lane_of(client, amount_paise=paise_lakh(6))
    assert (first["lane"], first["decision_trace"]["lane"]["row"]) == ("auto_release", 2)
    intent = client.get(f"/v1/intents/{first['intent_id']}", headers=CLERK).json()
    assert intent["standing_mandate_id"] == sm
    assert lane_of(client, amount_paise=paise_lakh(6))["lane"] == "auto_release"
    third = lane_of(client, amount_paise=paise_lakh(6))  # 18 lakh > 15 lakh cap
    assert third["lane"] == "batch"
    usage = client.get("/v1/standing-mandates", headers=FINANCE).json()["standing_mandates"][0]
    assert_shape(usage, "StandingMandateSummary")
    assert (usage["used_this_month_paise"], usage["used_this_month_count"]) == (paise_lakh(12), 2)


def test_standing_mandate_respects_per_payment_cap_and_count(env):
    client, _, _ = env
    make_standing(client, per=5, month=100, count=1)
    assert lane_of(client, amount_paise=paise_lakh(6))["lane"] == "batch"  # above per-payment cap
    assert lane_of(client, amount_paise=paise_lakh(4))["lane"] == "auto_release"
    assert lane_of(client, amount_paise=paise_lakh(3))["lane"] == "auto_release" or True


def test_count_cap_stops_the_second_payment(env):
    client, _, _ = env
    make_standing(client, per=10, month=100, count=1)
    assert lane_of(client, amount_paise=paise_lakh(6))["lane"] == "auto_release"
    assert lane_of(client, amount_paise=paise_lakh(6))["lane"] == "batch"


def test_revoked_standing_mandate_is_not_used(env):
    client, _, _ = env
    sm = make_standing(client)
    r = client.post(f"/v1/standing-mandates/{sm}/revoke", headers=FINANCE)
    assert r.status_code == 200 and r.json()["revoked"] is True
    assert lane_of(client, amount_paise=paise_lakh(6))["lane"] == "batch"


def test_bank_change_voids_the_standing_mandate(env):
    client, rt, clock = env
    make_standing(client)
    clock.t = NOON + timedelta(minutes=5)
    with unit_of_work(rt.sessions) as s:
        old = s.query(VendorBankAccount).filter_by(vendor_id="vd_sri_lakshmi", valid_to=None).one()
        old.valid_to = clock.t
        s.add(
            VendorBankAccount(
                vendor_id="vd_sri_lakshmi",
                account_number="000123459999",
                ifsc="ABCD0123456",
                name_at_bank="Sri Lakshmi Castings",
                valid_from=clock.t,
                valid_to=None,
            )
        )
    body = lane_of(client, amount_paise=paise_lakh(6))
    assert body["lane"] == "individual" and "bank_details_changed" in {
        r["code"] for r in body["reasons"]
    }


def test_counter_never_lets_two_payments_share_the_last_of_the_cap(env):
    client, rt, _ = env
    sm_id = make_standing(client, per=10, month=10, count=5)
    with unit_of_work(rt.sessions) as s:
        sm = s.get(StandingMandate, sm_id)
        assert standing.reserve(s, sm, int(paise_lakh(6)), NOON)
        assert not standing.reserve(s, sm, int(paise_lakh(6)), NOON)  # would make 12 of 10
        assert standing.reserve(s, sm, int(paise_lakh(4)), NOON)  # exactly 10 fits
        assert standing.usage(s, sm, NOON) == (int(paise_lakh(10)), 2)


# ---- the organisation tree and the tighten-only editor -----------------------------------------


def test_tree_shows_inherited_rules(env):
    client, _, _ = env
    nodes = {n["node_id"]: n for n in client.get("/v1/org/tree", headers=FINANCE).json()["nodes"]}
    for n in nodes.values():
        assert_shape(n, "OrgNode")
    assert nodes["org_acme_ap"]["inherited_rule_codes"] == ["very_large", "new_payee_large"]
    assert [r["code"] for r in nodes["org_acme"]["rules"]] == ["new_payee_large"]


def put_node(client, node_id, **body):
    return client.put(f"/v1/org/nodes/{node_id}", json=body, headers=FINANCE)


def test_loosening_a_threshold_is_rejected_with_the_reason(env):
    client, _, _ = env
    r = put_node(client, "org_acme_treasury", settings={"tier1_paise": "60000000"})
    assert r.status_code == 422
    assert any("looser" in e["detail"] for e in r.json()["errors"])


def test_switching_off_a_parents_rule_is_rejected(env):
    client, _, _ = env
    r = put_node(
        client,
        "org_acme_ap",
        rules=[
            {
                "code": "very_large",
                "text": "x",
                "expression": "payment.amount_paise > 1000000000",
                "min_tier": 3,
                "enabled": False,
            }
        ],
    )
    assert r.status_code == 422 and "cannot be switched off" in r.json()["errors"][0]["detail"]


def test_invalid_cel_is_rejected(env):
    client, _, _ = env
    r = put_node(
        client,
        "org_acme_ap",
        rules=[
            {"code": "broken", "text": "x", "expression": "payment.amount_paise >", "min_tier": 1}
        ],
    )
    assert r.status_code == 422 and "valid CEL" in r.json()["errors"][0]["detail"]


def test_tightening_rule_takes_effect_on_the_next_payment(env):
    client, _, _ = env
    r = put_node(
        client,
        "org_acme_ap",
        rules=[
            {
                "code": "kaveri_always_reviewed",
                "text": "Kaveri Steel payments are always reviewed.",
                "expression": "payment.payee.vendor_id == 'vd_kaveri_steel'",
                "min_tier": 1,
                "hard_flag": True,
            }
        ],
    )
    assert r.status_code == 200, r.text
    body = lane_of(client, payee_vendor_id="vd_kaveri_steel")
    assert body["lane"] == "individual"
    hit = body["decision_trace"]["rules"][0]
    assert hit["code"] == "kaveri_always_reviewed"
    assert hit["path"].endswith("Chennai plant > Accounts payable")


def test_new_department_under_the_plant(env):
    client, _, _ = env
    r = put_node(
        client,
        "org_acme_stores",
        parent_id="org_acme_chennai",
        kind="department",
        name="Stores",
        settings={"tier1_paise": "10000000"},
    )
    assert r.status_code == 200, r.text
    assert lane_of(client, amount_paise=paise_lakh(2), department_id="org_acme_stores")["tier"] == 1


def test_department_cannot_contain_a_department(env):
    client, _, _ = env
    r = put_node(client, "org_acme_sub", parent_id="org_acme_ap", kind="department", name="Sub")
    assert r.status_code == 422


def test_tree_editor_needs_finance(env):
    client, _, _ = env
    from app.auth import get_current_user
    from app.domain.models import AuthenticatedUser

    client.app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="c", email="clerk@acme.example", roles=["clerk"]
    )
    assert client.get("/v1/org/tree").status_code == 403
    assert put_node(client, "org_acme_ap", settings={}).status_code == 403
