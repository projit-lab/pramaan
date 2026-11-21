"""End-to-end test for the AI agent payment flow: /agent/pay and /agent-requests."""

import pytest
from tests.test_m2_api import CLERK, as_user


def test_agent_pay_poisoned_invoice_flow(env):
    client, rt, _ = env

    # 1. Post poisoned invoice KAVERI-4471 to /agent/pay
    r = client.post("/v1/agent/pay", json={"invoice_ref": "KAVERI-4471"}, headers=CLERK)
    assert r.status_code == 202
    body = r.json()
    agent_req_id = body["agent_request_id"]
    assert agent_req_id.startswith("ag_")

    # 2. Get the agent request
    req_r = client.get(f"/v1/agent-requests/{agent_req_id}", headers=CLERK)
    assert req_r.status_code == 200
    req = req_r.json()
    assert req["status"] == "flagged"
    assert req["modelArmorFinding"] is not None
    assert req["modelArmorFinding"]["category"] == "prompt_injection"
    assert "000123458117" in req["modelArmorFinding"]["excerpt"]
    assert len(req["log"]) == 5

    # 3. Intent was created and held
    intent_id = req["intentId"]
    assert intent_id.startswith("pi_")
    intent_r = client.get(f"/v1/intents/{intent_id}", headers=CLERK)
    assert intent_r.status_code == 200
    intent = intent_r.json()
    assert intent["status"] == "held"
    assert intent["tier"] >= 2
    assert intent["entry_route"] == "agent"


def test_agent_pay_clean_invoice_flow(env):
    client, rt, _ = env

    r = client.post("/v1/agent/pay", json={"invoice_ref": "INV-2219"}, headers=CLERK)
    assert r.status_code == 202
    agent_req_id = r.json()["agent_request_id"]

    req_r = client.get(f"/v1/agent-requests/{agent_req_id}", headers=CLERK)
    assert req_r.status_code == 200
    req = req_r.json()
    assert req["status"] == "mandate_requested"
    assert req["modelArmorFinding"] is None
