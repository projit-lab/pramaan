"""Tests for Payables Agent Safety Invariants.

Absolute Safety Rule: Never write code that lets an AI agent release a payment.
"""

import pytest
from pramaan_agent.payables_agent import PayablesAgent
from pramaan_agent.tools import AgentTool, PayablesToolRegistry, SecurityViolationError


def dummy_create_intent(**kwargs):
    return {"intent_id": "pi_dummy", "status": "held", "tier": 2, "decision": "hold"}


def test_agent_tool_registry_allows_only_create_intent():
    registry = PayablesToolRegistry()
    create_tool = AgentTool(
        name="create_intent",
        description="Creates payment intent",
        parameters={},
        fn=dummy_create_intent,
    )
    registry.register(create_tool)
    assert len(registry.tools) == 1
    assert registry.tools[0].name == "create_intent"
    registry.verify_safety_invariants()


@pytest.mark.parametrize(
    "forbidden_tool",
    [
        "release_payment",
        "approve_payment",
        "sign_mandate",
        "bypass_approval",
        "execute_payout",
        "alter_payment",
        "transfer_funds",
        "mark_paid",
    ],
)
def test_registering_release_or_approval_tool_is_strictly_forbidden(forbidden_tool):
    registry = PayablesToolRegistry()
    tool = AgentTool(
        name=forbidden_tool,
        description="Dangerous tool",
        parameters={},
        fn=lambda **kw: None,
    )
    with pytest.raises(SecurityViolationError, match="Absolute Safety Rule Violation"):
        registry.register(tool)


def test_agent_cannot_have_more_than_one_tool():
    registry = PayablesToolRegistry()
    tool1 = AgentTool(
        name="create_intent",
        description="Intent creation",
        parameters={},
        fn=dummy_create_intent,
    )
    registry.register(tool1)

    tool2 = AgentTool(
        name="query_invoices",
        description="Read invoices",
        parameters={},
        fn=lambda **kw: None,
    )
    with pytest.raises(SecurityViolationError):
        registry.register(tool2)


def test_payables_agent_safety_methods():
    agent = PayablesAgent(create_intent_fn=dummy_create_intent)
    assert len(agent.tools) == 1
    assert agent.tools[0].name == "create_intent"

    with pytest.raises(SecurityViolationError, match="Agent has no authority to release payments"):
        agent.release_payment()

    with pytest.raises(SecurityViolationError, match="Agent cannot approve payments"):
        agent.approve_payment()
