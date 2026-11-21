"""POST /agent/pay and GET /agent-requests endpoints (contracts/openapi.yaml)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path as FastPath, status
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import AuthenticatedUser
from app.errors import ProblemException
from app.roles import require_roles
from app.runtime import Runtime, get_runtime
from app.services.intents import create_intent
from app.routers.intents import IntentCreate, InitiatorIn

# Import agent service modules
import sys
AGENT_DIR = Path(__file__).resolve().parents[4] / "services" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from pramaan_agent.payables_agent import PayablesAgent

logger = logging.getLogger("pramaan")

router = APIRouter(tags=["agent"])

INVOICES_DIR = Path(__file__).resolve().parents[4] / "data" / "invoices"
AGENT_DIR = Path(__file__).resolve().parents[4] / "services" / "agent"

# In-memory store for agent requests if read_model is in-memory
_AGENT_REQUESTS: dict[str, dict[str, Any]] = {}


class AgentPayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_ref: str = Field(min_length=1, max_length=100)


@router.post("/agent/pay", status_code=status.HTTP_202_ACCEPTED, operation_id="agentPay")
def post_agent_pay(
    body: AgentPayIn,
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance")),
):
    """Hands an invoice to the payables agent.

    The agent reads the invoice, scans with Model Armor, runs deterministic rules
    against the vendor master, and calls create_intent. It cannot release money.
    """
    ref = body.invoice_ref.strip()
    pdf_filename = ref if ref.endswith(".pdf") else f"{ref}.pdf"
    pdf_path = INVOICES_DIR / pdf_filename

    if not pdf_path.exists():
        raise ProblemException(
            404,
            "Invoice file not found",
            f"No demo invoice file found for reference '{body.invoice_ref}'.",
        )

    def agent_create_intent(**kw: Any) -> dict[str, Any]:
        intent_in = IntentCreate(
            payee_vendor_id=kw["payee_vendor_id"],
            amount_paise=kw["amount_paise"],
            purpose=kw["purpose"],
            invoice_sha256=kw.get("invoice_sha256"),
            instruction_channel="agent",
            entry_route="agent",
            initiator=InitiatorIn(type="agent", id=kw["initiator"]["id"]),
        )
        created = create_intent(rt, intent_in)
        return created

    agent = PayablesAgent(create_intent_fn=agent_create_intent)
    result = agent.process_invoice(pdf_path)

    # Store agent request in read model and cache
    agent_req_dict = result.to_agent_request_dict()
    _AGENT_REQUESTS[result.agent_request_id] = agent_req_dict

    try:
        rt.read_model.set_document("agentRequests", result.agent_request_id, agent_req_dict)
    except Exception as e:
        logger.warning(f"Could not set agentRequests doc in read model: {e}")

    # Update hold document and DB with rich agent context (Model Armor, Invoice extraction, etc.)
    if result.intent_id:
        from app.db.engine import unit_of_work
        from app.db.models import PaymentIntent
        
        tier_to_set = max(result.tier, 2) if (result.model_armor_finding or result.reasons) else result.tier
        all_reasons = []
        with unit_of_work(rt.sessions) as s:
            pi = s.get(PaymentIntent, result.intent_id)
            if pi:
                pi.tier = tier_to_set
                cur_codes = {r.get("code") for r in pi.reasons}
                reasons = list(pi.reasons)
                for r in result.reasons:
                    if r.get("code") not in cur_codes:
                        reasons.append(r)
                        cur_codes.add(r.get("code"))
                if result.model_armor_finding and "model_armor_finding" not in cur_codes:
                    reasons.append({
                        "code": "model_armor_finding",
                        "text": "The invoice contains a hidden instruction.",
                        "source": "model_armor",
                    })
                pi.reasons = reasons
                all_reasons = reasons

        update_data = {
            "tier": tier_to_set,
            "reasons": all_reasons,
            "modelArmorFinding": result.model_armor_finding.to_firestore_dict() if result.model_armor_finding else None,
            "invoice": result.invoice_doc,
            "agentRequestId": result.agent_request_id,
            "entryRoute": "agent",
        }
        try:
            rt.read_model.update_document("holds", result.intent_id, update_data)
        except Exception as e:
            logger.warning(f"Could not update hold {result.intent_id} with agent context: {e}")

    return {"agent_request_id": result.agent_request_id}


@router.get("/agent-requests", operation_id="listAgentRequests")
def list_agent_requests(
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance")),
):
    return {"agent_requests": list(_AGENT_REQUESTS.values())}


@router.get("/agent-requests/{agentRequestId}", operation_id="getAgentRequest")
def get_agent_request(
    agent_request_id: Annotated[str, FastPath(alias="agentRequestId", pattern=r"^ag_[A-Za-z0-9]+$")],
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance")),
):
    req = _AGENT_REQUESTS.get(agent_request_id)
    if not req:
        doc = rt.read_model.get_document("agentRequests", agent_request_id)
        if doc:
            req = doc
    if not req:
        raise ProblemException(404, "Not found", f"No agent request '{agent_request_id}'.")
    return req
