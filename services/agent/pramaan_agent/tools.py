"""ADK tools for the Pramaan Payables Agent.

ABSOLUTE SAFETY RULE:
Never write code that lets an AI agent release or approve a payment.
The payables agent has EXACTLY ONE tool: create_intent.
It has NO tool for releasing money, approving payments, signing mandates,
or altering bank account details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class SecurityViolationError(Exception):
    """Raised when an attempt is made to grant an agent forbidden capabilities."""


FORBIDDEN_ACTIONS = frozenset(
    {
        "release_payment",
        "approve_payment",
        "sign_mandate",
        "bypass_approval",
        "execute_payout",
        "alter_payment",
        "alter_vendor_master",
        "transfer_funds",
        "mark_paid",
    }
)


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


class PayablesToolRegistry:
    """Strict tool registry for the payables agent.

    Guarantees:
    1. Exactly ONE tool can be registered: 'create_intent'.
    2. Attempting to register any approval/release/bypass tool immediately raises SecurityViolationError.
    3. Tool count is locked at 1.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if tool.name in FORBIDDEN_ACTIONS:
            raise SecurityViolationError(
                f"Absolute Safety Rule Violation: Agent cannot have tool '{tool.name}'. "
                "All payments require explicit cryptographic human approval with a phone's hardware-backed key."
            )
        if tool.name != "create_intent":
            raise SecurityViolationError(
                f"Unauthorized tool '{tool.name}'. The payables agent must have strictly ONE tool: create_intent."
            )
        if len(self._tools) >= 1 and tool.name not in self._tools:
            raise SecurityViolationError(
                "Tool capacity exceeded. The payables agent must have exactly ONE tool."
            )
        self._tools[tool.name] = tool

    @property
    def tools(self) -> list[AgentTool]:
        return list(self._tools.values())

    def get(self, name: str) -> AgentTool:
        if name in FORBIDDEN_ACTIONS:
            raise SecurityViolationError(f"Tool '{name}' is forbidden by safety rules.")
        if name not in self._tools:
            raise KeyError(f"No such tool: {name}")
        return self._tools[name]

    def verify_safety_invariants(self) -> None:
        if len(self._tools) != 1:
            raise SecurityViolationError(
                f"Expected exactly 1 tool, found {len(self._tools)}. Agent must have strictly ONE tool."
            )
        if "create_intent" not in self._tools:
            raise SecurityViolationError("Mandatory tool 'create_intent' is missing.")
        for forbidden in FORBIDDEN_ACTIONS:
            if forbidden in self._tools:
                raise SecurityViolationError(f"Forbidden tool '{forbidden}' found in agent registry!")
