"""POST /v1/intents and GET /v1/intents/{intentId} (contracts/openapi.yaml)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.engine import unit_of_work
from app.db.models import PaymentIntent
from app.domain.models import AuthenticatedUser
from app.domain.money import parse_paise
from app.errors import ProblemException
from app.roles import require_roles
from app.runtime import Runtime, get_runtime
from app.services.intents import create_intent
from app.services.views import intent_view

router = APIRouter(tags=["intents"])

IFSC = r"^[A-Z]{4}0[A-Z0-9]{6}$"


class PayeeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_at_bank: str = Field(min_length=1, max_length=200)
    account_last4: str = Field(pattern=r"^[0-9]{4}$")
    ifsc: str = Field(pattern=IFSC)
    vendor_id: str | None = None


class InitiatorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["human", "agent"]
    id: str = Field(min_length=1, max_length=254)


class IntentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payee_vendor_id: str | None = Field(default=None, pattern=r"^vd_[A-Za-z0-9_]+$")
    payee: PayeeIn | None = None
    amount_paise: str
    currency: Literal["INR"] = "INR"
    purpose: str | None = Field(default=None, max_length=200)
    invoice_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    instruction_channel: Literal["portal", "email", "chat", "phone", "agent"]
    instruction_note: str | None = Field(default=None, max_length=2000)
    initiator: InitiatorIn
    # M2+: where in the organisation the payment belongs; defaults to the
    # company's accounts-payable department.
    department_id: str | None = Field(default=None, pattern=r"^org_[A-Za-z0-9_]+$")
    # The system the payment came in through. Defaults from the initiator.
    entry_route: Literal["erp", "bank_file", "payout_api", "agent"] | None = None

    @property
    def route(self) -> str:
        if self.entry_route:
            return self.entry_route
        return "agent" if self.initiator.type == "agent" else "erp"

    @model_validator(mode="after")
    def _check(self) -> IntentCreate:
        if (self.payee_vendor_id is None) == (self.payee is None):
            raise ValueError("give exactly one of payee_vendor_id or payee")
        parse_paise(self.amount_paise)
        return self

    @property
    def amount(self) -> int:
        return parse_paise(self.amount_paise)


@router.post("/intents", status_code=status.HTTP_201_CREATED, operation_id="createIntent")
def post_intent(
    body: IntentCreate,
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("clerk", "finance", "agent")),
):
    return create_intent(rt, body)


@router.get("/intents/{intentId}", operation_id="getIntent")
def get_intent(
    intent_id: Annotated[str, Path(alias="intentId", pattern=r"^pi_[A-Za-z0-9]+$")],
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("finance", "clerk")),
):
    with unit_of_work(rt.sessions) as s:
        intent = s.get(PaymentIntent, intent_id)
        if intent is None or intent.company_id != rt.settings.COMPANY_ID:
            raise ProblemException(404, "Not found", "No such payment.")
        return intent_view(intent)
