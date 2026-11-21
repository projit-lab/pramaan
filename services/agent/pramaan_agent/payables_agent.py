"""ADK Payables Agent.

ABSOLUTE SAFETY RULE:
Never write code that lets an AI agent release or approve a payment.
All payments require explicit cryptographic human approval with a phone's hardware-backed key.

The payables agent:
1. Has strictly ONE tool: create_intent.
2. Reads the invoice PDF.
3. Model Armor scans for prompt injection payloads.
4. Rules compare the extracted account against the Vendor Master.
5. Either Model Armor finding or account mismatch raises the tier (Tier 2/3).
6. The agent creates the intent (holding the payment for an approver's phone).
7. The agent STOPS. It has no tool that releases money.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pramaan_agent.extractor import InvoiceExtractor
from pramaan_agent.model_armor import ModelArmorFinding, ModelArmorScanner
from pramaan_agent.tools import AgentTool, PayablesToolRegistry, SecurityViolationError

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def format_inr(paise: int) -> str:
    rupees = paise // 100
    s = str(rupees)
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return ",".join(parts) + "," + last3


@dataclass(frozen=True)
class AgentRunResult:
    agent_request_id: str
    agent_id: str
    invoice_ref: str
    intent_id: str | None
    status: str  # flagged, mandate_requested, held, failed
    model_armor_finding: ModelArmorFinding | None
    invoice_doc: dict[str, Any]
    reasons: list[dict[str, Any]]
    log: list[dict[str, str]]
    tier: int
    decision: str  # hold
    held: bool = True

    def to_agent_request_dict(self) -> dict[str, Any]:
        return {
            "agentRequestId": self.agent_request_id,
            "agentId": self.agent_id,
            "invoiceRef": self.invoice_ref,
            "intentId": self.intent_id,
            "status": self.status,
            "modelArmorFinding": self.model_armor_finding.to_firestore_dict() if self.model_armor_finding else None,
            "log": self.log,
            "createdAt": now_ist(),
        }


class PayablesAgent:
    """The Autonomous Payables Agent.

    Strictly bound by safety invariants: exactly ONE tool (create_intent).
    """

    def __init__(
        self,
        create_intent_fn: Callable[..., Any],
        agent_id: str = "payables-agent-01",
        vendor_master: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.registry = PayablesToolRegistry()

        create_tool = AgentTool(
            name="create_intent",
            description="Create a payment intent in Pramaan. The payment will be scored by rules and held for human cryptographic approval.",
            parameters={
                "type": "object",
                "required": ["payee_vendor_id", "amount_paise", "purpose", "instruction_channel", "initiator"],
                "properties": {
                    "payee_vendor_id": {"type": "string"},
                    "amount_paise": {"type": "string"},
                    "purpose": {"type": "string"},
                    "invoice_sha256": {"type": "string"},
                    "instruction_channel": {"type": "string", "enum": ["agent"]},
                    "entry_route": {"type": "string", "enum": ["agent"]},
                    "initiator": {"type": "object"},
                },
            },
            fn=create_intent_fn,
        )
        self.registry.register(create_tool)
        self.registry.verify_safety_invariants()

        self.scanner = ModelArmorScanner()
        self.extractor = InvoiceExtractor(vendor_master=vendor_master)

    @property
    def tools(self) -> list[AgentTool]:
        self.registry.verify_safety_invariants()
        return self.registry.tools

    def process_invoice(
        self,
        pdf_path_or_bytes: str | Path | bytes,
        vendor_id: str | None = None,
    ) -> AgentRunResult:
        # Verify invariants before running
        self.registry.verify_safety_invariants()

        agent_req_id = f"ag_{secrets.token_hex(8)}"
        log: list[dict[str, str]] = []

        # 1. Read & Extract
        extracted = self.extractor.extract_from_pdf(pdf_path_or_bytes)
        log.append({
            "at": now_ist(),
            "text": f"Reading invoice {extracted.invoice_ref}.",
            "source": "rule",
        })

        # 2. Model Extraction note
        account_last4 = extracted.account_extracted[-4:] if extracted.account_extracted else "????"
        amount_fmt = format_inr(extracted.amount_paise)
        log.append({
            "at": now_ist(),
            "text": f"Read: vendor {extracted.vendor_name}, amount Rupees {amount_fmt}, account ending {account_last4}.",
            "source": "gemini",
        })

        # 3. Model Armor scan
        finding = self.scanner.scan(extracted.raw_text)
        if finding:
            log.append({
                "at": now_ist(),
                "text": "Model Armor finding: the invoice contains a hidden instruction.",
                "source": "model_armor",
            })

        # 4. Deterministic comparison against Vendor Master
        invoice_doc, rule_reasons, matched_vid = self.extractor.compare_with_vendor_master(
            extracted, vendor_id=vendor_id
        )

        has_mismatch = any(r["code"] == "invoice_account_mismatch" for r in rule_reasons)
        if has_mismatch:
            master_rec = self.extractor.vendor_master.get(matched_vid, {})
            master_last4 = master_rec.get("account_last4", master_rec.get("account_number", "")[-4:])
            log.append({
                "at": now_ist(),
                "text": f"Vendor master says account ending {master_last4}. The accounts do not match.",
                "source": "rule",
            })

        # 5. Intent payload
        tool = self.registry.get("create_intent")
        intent_payload = {
            "payee_vendor_id": matched_vid,
            "amount_paise": str(extracted.amount_paise),
            "purpose": extracted.invoice_ref,
            "invoice_sha256": extracted.sha256,
            "instruction_channel": "agent",
            "entry_route": "agent",
            "initiator": {"type": "agent", "id": self.agent_id},
            # Extra context passed to intent engine/read model
            "model_armor_finding": finding.to_dict() if finding else None,
            "invoice_doc": invoice_doc,
            "rule_reasons": rule_reasons,
            "agent_request_id": agent_req_id,
        }

        # 6. Execute create_intent tool
        log.append({
            "at": now_ist(),
            "text": "Requested a mandate. The agent has no tool that releases money.",
            "source": "rule",
        })

        intent_res = tool(**intent_payload)
        intent_id = intent_res.get("intent_id") if isinstance(intent_res, dict) else str(intent_res)
        tier = intent_res.get("tier", 2) if isinstance(intent_res, dict) else 2
        decision = intent_res.get("decision", "hold") if isinstance(intent_res, dict) else "hold"

        # Determine agent request status
        status = "flagged" if (finding is not None or has_mismatch) else "mandate_requested"

        return AgentRunResult(
            agent_request_id=agent_req_id,
            agent_id=self.agent_id,
            invoice_ref=extracted.invoice_ref,
            intent_id=intent_id,
            status=status,
            model_armor_finding=finding,
            invoice_doc=invoice_doc,
            reasons=rule_reasons,
            log=log,
            tier=tier,
            decision=decision,
            held=True,
        )

    # Explicitly prohibit release methods
    def release_payment(self, *args: Any, **kwargs: Any) -> None:
        raise SecurityViolationError("Absolute Safety Rule Violation: Agent has no authority to release payments.")

    def approve_payment(self, *args: Any, **kwargs: Any) -> None:
        raise SecurityViolationError("Absolute Safety Rule Violation: Agent cannot approve payments.")
