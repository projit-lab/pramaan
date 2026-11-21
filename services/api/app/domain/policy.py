"""Policy engine v1 (M2, Danish; Prajit reviews the rules).

Deterministic rules decide; no model is involved. The same facts and policy
always give the same tier, so auditors can test it. This is the base the M2+
hierarchy engine builds on.

The six rules (codes as in contracts/openapi.yaml, GET /policies):
  new_payee              first payment to this payee
  bank_details_changed   the payee's bank details changed in the last 30 days
  amount_above_5_lakh    amount above the policy's tier1 threshold (and the higher
                         tier2 / tier3 thresholds, reported as amount_above_25_lakh ...)
  outside_working_hours  raised outside the policy's working hours (IST)
  raised_by_agent        raised by an AI agent
  instruction_by_chat    the instruction arrived by chat or email

Tiers (product document, "Tier When it applies"):
  0  no rule fired                                   -> release
  1  any rule fired                                  -> hold, signed approval
  2  amount above tier2, or SEVERAL_SIGNALS rules    -> hold, plus spoken check
     fired together
  3  amount above tier3, or the first payment to a   -> hold, two people and a
     bank account changed in the last 30 days that      call-back
     is above FIRST_PAYMENT_TO_CHANGED_ACCOUNT_LIMIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any

from app.domain.money import LAKH, rupees_text, threshold_label

IST = timezone(timedelta(hours=5, minutes=30))

BANK_CHANGE_WINDOW = timedelta(days=30)
SEVERAL_SIGNALS = 3
FIRST_PAYMENT_TO_CHANGED_ACCOUNT_LIMIT = 10 * LAKH  # paise; Rs 10 lakh

RULE_CODES = (
    "new_payee",
    "bank_details_changed",
    "amount_above_5_lakh",
    "outside_working_hours",
    "raised_by_agent",
    "instruction_by_chat",
)


class PolicyError(ValueError):
    """The stored policy document is unusable; fail closed rather than guess."""


@dataclass(frozen=True)
class PolicyDocument:
    version: str
    tier1_paise: int
    tier2_paise: int
    tier3_paise: int
    working_start: time
    working_end: time
    enabled: frozenset[str]
    rule_text: dict[str, str]
    approval_matrix: tuple[tuple[int | None, tuple[str, ...]], ...]

    @classmethod
    def from_contract(cls, doc: dict[str, Any]) -> PolicyDocument:
        """Build from the contract's PolicySet JSON (as served by GET /policies)."""
        try:
            th = doc["tier_thresholds_paise"]
            t1, t2, t3 = int(th["tier1"]), int(th["tier2"]), int(th["tier3"])
            hours = doc.get("working_hours_ist") or {"start": "09:00", "end": "19:00"}
            start = time.fromisoformat(hours["start"])
            end = time.fromisoformat(hours["end"])
            rules = doc["rules"]
            matrix = tuple(
                (
                    None if row.get("up_to_paise") is None else int(row["up_to_paise"]),
                    tuple(row["approvers"]),
                )
                for row in doc.get("approval_matrix", [])
            )
        except (KeyError, TypeError, ValueError) as e:
            raise PolicyError(f"policy document is incomplete: {e}") from e
        if not (0 < t1 < t2 < t3):
            raise PolicyError("tier thresholds must rise: tier1 < tier2 < tier3")
        if not matrix or matrix[-1][0] is not None:
            raise PolicyError(
                "the approval matrix must end with an open-ended row (up_to_paise null)"
            )
        return cls(
            version=str(doc["version"]),
            tier1_paise=t1,
            tier2_paise=t2,
            tier3_paise=t3,
            working_start=start,
            working_end=end,
            enabled=frozenset(r["code"] for r in rules if r.get("enabled")),
            rule_text={r["code"]: r["text"] for r in rules},
            approval_matrix=matrix,
        )


@dataclass(frozen=True)
class PaymentFacts:
    """Everything the rules look at, gathered before evaluation."""

    amount_paise: int
    created_at: datetime
    instruction_channel: str
    initiator_type: str
    payee_is_new: bool
    bank_changed_at: datetime | None = None
    # True when no earlier payment went to the payee's current account.
    first_payment_to_current_account: bool = True


@dataclass(frozen=True)
class PolicyResult:
    tier: int
    decision: str  # release or hold
    status: str  # approved (tier 0, passed the rules) or held
    reasons: list[dict[str, Any]] = field(default_factory=list)
    policy_version: str = ""

    @property
    def codes(self) -> list[str]:
        return [r["code"] for r in self.reasons]


def _reason(code: str, text: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "text": text, "source": "rule", **extra}


def _in_working_hours(at: datetime, start: time, end: time) -> bool:
    local = at.astimezone(IST).time()
    return start <= local < end


def evaluate(facts: PaymentFacts, policy: PolicyDocument) -> PolicyResult:
    if facts.created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    on = policy.enabled
    text = policy.rule_text
    reasons: list[dict[str, Any]] = []

    bank_recently_changed = (
        facts.bank_changed_at is not None
        and facts.created_at - facts.bank_changed_at <= BANK_CHANGE_WINDOW
    )

    if "new_payee" in on and facts.payee_is_new:
        reasons.append(_reason("new_payee", text.get("new_payee", "First payment to this payee.")))

    if "bank_details_changed" in on and bank_recently_changed:
        reasons.append(
            _reason(
                "bank_details_changed",
                text.get(
                    "bank_details_changed", "The payee's bank details changed in the last 30 days."
                ),
                changed_at=facts.bank_changed_at.astimezone(IST).isoformat(timespec="seconds"),
            )
        )

    amount_rule = "amount_above_5_lakh" in on
    if amount_rule:
        crossed = [
            t
            for t in (policy.tier3_paise, policy.tier2_paise, policy.tier1_paise)
            if facts.amount_paise > t
        ]
        if crossed:
            top = crossed[0]
            reasons.append(
                _reason(
                    f"amount_above_{threshold_label(top)}", f"Amount is above {rupees_text(top)}."
                )
            )

    if "outside_working_hours" in on and not _in_working_hours(
        facts.created_at, policy.working_start, policy.working_end
    ):
        reasons.append(
            _reason(
                "outside_working_hours",
                text.get("outside_working_hours", "Raised outside working hours."),
            )
        )

    if "raised_by_agent" in on and (
        facts.initiator_type == "agent" or facts.instruction_channel == "agent"
    ):
        reasons.append(
            _reason("raised_by_agent", text.get("raised_by_agent", "Raised by an AI agent."))
        )

    if "instruction_by_chat" in on and facts.instruction_channel in ("chat", "email"):
        reasons.append(
            _reason(
                "instruction_by_chat",
                f"The instruction arrived by {facts.instruction_channel}.",
            )
        )

    tier = 1 if reasons else 0
    if amount_rule and facts.amount_paise > policy.tier2_paise:
        tier = max(tier, 2)
    if len(reasons) >= SEVERAL_SIGNALS:
        tier = max(tier, 2)
    if amount_rule and facts.amount_paise > policy.tier3_paise:
        tier = 3
    if (
        bank_recently_changed
        and facts.first_payment_to_current_account
        and facts.amount_paise > FIRST_PAYMENT_TO_CHANGED_ACCOUNT_LIMIT
    ):
        tier = 3

    if tier == 0:
        return PolicyResult(0, "release", "approved", [], policy.version)
    return PolicyResult(tier, "hold", "held", reasons, policy.version)


def approvers_for(amount_paise: int, policy: PolicyDocument) -> tuple[str, ...]:
    """First row of the approval matrix whose ceiling covers the amount."""
    for ceiling, approvers in policy.approval_matrix:
        if ceiling is None or amount_paise <= ceiling:
            return approvers
    raise PolicyError("no approval matrix row covers this amount")  # unreachable after validation
