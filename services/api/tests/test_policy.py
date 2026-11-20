"""Policy engine v1: one test per rule, plus tier boundaries and the approval matrix.

The policy under test is the contract's own GET /policies example, so a change to
the published policy shows up here.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from app.domain.money import indian_grouping, parse_paise, rupees_text, threshold_label
from app.domain.policy import (
    IST,
    PaymentFacts,
    PolicyDocument,
    PolicyError,
    approvers_for,
    evaluate,
)

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"
LAKH = 100_000 * 100


def contract_policy() -> dict:
    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    return spec["paths"]["/policies"]["get"]["responses"]["200"]["content"]["application/json"][
        "example"
    ]


@pytest.fixture(scope="module")
def policy() -> PolicyDocument:
    return PolicyDocument.from_contract(contract_policy())


NOON = datetime(2026, 11, 20, 12, 0, tzinfo=IST)


def facts(**kw) -> PaymentFacts:
    base = dict(
        amount_paise=1 * LAKH,
        created_at=NOON,
        instruction_channel="portal",
        initiator_type="human",
        payee_is_new=False,
        bank_changed_at=None,
        first_payment_to_current_account=False,
    )
    base.update(kw)
    return PaymentFacts(**base)


# ---- the contract policy itself ---------------------------------------------


def test_contract_policy_loads(policy):
    assert policy.version == "2026.11.1"
    assert (policy.tier1_paise, policy.tier2_paise) == (5 * LAKH, 25 * LAKH)
    assert len(policy.enabled) == 6


# ---- one test per rule --------------------------------------------------------


def test_clean_payment_passes_at_tier_0(policy):
    r = evaluate(facts(), policy)
    assert (r.tier, r.decision, r.status, r.reasons) == (0, "release", "approved", [])
    assert r.policy_version == "2026.11.1"


def test_rule_new_payee(policy):
    r = evaluate(facts(payee_is_new=True), policy)
    assert r.codes == ["new_payee"] and r.tier == 1 and r.decision == "hold"


def test_rule_bank_details_changed(policy):
    r = evaluate(facts(bank_changed_at=NOON - timedelta(days=3)), policy)
    assert r.codes == ["bank_details_changed"] and r.tier == 1
    assert r.reasons[0]["changed_at"].endswith("+05:30")


def test_rule_amount_above_5_lakh(policy):
    r = evaluate(facts(amount_paise=5 * LAKH + 1), policy)
    assert r.codes == ["amount_above_5_lakh"] and r.tier == 1
    assert r.reasons[0]["text"] == "Amount is above Rupees 5,00,000."


def test_rule_outside_working_hours(policy):
    r = evaluate(facts(created_at=datetime(2026, 11, 20, 21, 30, tzinfo=IST)), policy)
    assert r.codes == ["outside_working_hours"] and r.tier == 1


def test_rule_raised_by_agent(policy):
    r = evaluate(facts(initiator_type="agent", instruction_channel="agent"), policy)
    assert r.codes == ["raised_by_agent"] and r.tier == 1


@pytest.mark.parametrize("channel", ["chat", "email"])
def test_rule_instruction_by_chat_or_email(policy, channel):
    r = evaluate(facts(instruction_channel=channel), policy)
    assert r.codes == ["instruction_by_chat"] and r.tier == 1
    assert channel in r.reasons[0]["text"]


# ---- boundaries -----------------------------------------------------------------


def test_exactly_5_lakh_is_not_above(policy):
    assert evaluate(facts(amount_paise=5 * LAKH), policy).tier == 0


def test_exactly_25_lakh_is_tier_1_not_2(policy):
    r = evaluate(facts(amount_paise=25 * LAKH), policy)
    assert (r.tier, r.codes) == (1, ["amount_above_5_lakh"])


def test_above_25_lakh_is_tier_2_and_reports_highest_threshold(policy):
    r = evaluate(facts(amount_paise=25 * LAKH + 1), policy)
    assert (r.tier, r.codes) == (2, ["amount_above_25_lakh"])


def test_above_tier3_threshold_is_tier_3(policy):
    r = evaluate(facts(amount_paise=policy.tier3_paise + 1), policy)
    assert r.tier == 3 and r.codes == [f"amount_above_{threshold_label(policy.tier3_paise)}"]


@pytest.mark.parametrize(
    "hh,mm,inside",
    [(8, 59, False), (9, 0, True), (18, 59, True), (19, 0, False)],
)
def test_working_hours_edges(policy, hh, mm, inside):
    r = evaluate(facts(created_at=datetime(2026, 11, 20, hh, mm, tzinfo=IST)), policy)
    assert ("outside_working_hours" in r.codes) is (not inside)


def test_working_hours_use_ist_even_when_given_utc(policy):
    from datetime import timezone

    utc_0400 = datetime(2026, 11, 20, 4, 0, tzinfo=timezone.utc)  # 09:30 IST
    assert evaluate(facts(created_at=utc_0400), policy).tier == 0


def test_bank_change_window_is_30_days(policy):
    inside = evaluate(facts(bank_changed_at=NOON - timedelta(days=30)), policy)
    outside = evaluate(facts(bank_changed_at=NOON - timedelta(days=30, seconds=1)), policy)
    assert "bank_details_changed" in inside.codes
    assert "bank_details_changed" not in outside.codes


def test_several_signals_raise_to_tier_2(policy):
    r = evaluate(
        facts(payee_is_new=True, instruction_channel="chat", amount_paise=6 * LAKH), policy
    )
    assert len(r.reasons) == 3 and r.tier == 2


def test_two_signals_stay_tier_1(policy):
    r = evaluate(facts(payee_is_new=True, instruction_channel="chat"), policy)
    assert len(r.reasons) == 2 and r.tier == 1


def test_first_payment_to_changed_account_above_10_lakh_is_tier_3(policy):
    f = dict(bank_changed_at=NOON - timedelta(days=3), first_payment_to_current_account=True)
    assert evaluate(facts(amount_paise=10 * LAKH + 1, **f), policy).tier == 3
    assert evaluate(facts(amount_paise=10 * LAKH, **f), policy).tier == 1


def test_changed_account_already_paid_is_not_tier_3(policy):
    r = evaluate(
        facts(
            amount_paise=12 * LAKH,
            bank_changed_at=NOON - timedelta(days=3),
            first_payment_to_current_account=False,
        ),
        policy,
    )
    assert r.tier == 1


def test_boss_scam_from_the_contract_example_is_tier_2(policy):
    """The contract's held example: Rs 46.5 lakh to a new payee, by chat."""
    r = evaluate(
        facts(amount_paise=465000000, payee_is_new=True, instruction_channel="chat"), policy
    )
    assert r.tier == 2
    assert r.codes == ["new_payee", "amount_above_25_lakh", "instruction_by_chat"]


def test_reason_order_and_source_are_stable(policy):
    r = evaluate(
        facts(
            payee_is_new=True,
            bank_changed_at=NOON - timedelta(days=1),
            amount_paise=6 * LAKH,
            created_at=datetime(2026, 11, 20, 22, 0, tzinfo=IST),
            initiator_type="agent",
            instruction_channel="agent",
        ),
        policy,
    )
    assert r.codes == [
        "new_payee",
        "bank_details_changed",
        "amount_above_5_lakh",
        "outside_working_hours",
        "raised_by_agent",
    ]
    assert all(x["source"] == "rule" for x in r.reasons)


def test_disabled_rule_does_not_fire():
    doc = contract_policy()
    doc["rules"] = [dict(r, enabled=r["code"] != "new_payee") for r in doc["rules"]]
    p = PolicyDocument.from_contract(doc)
    assert evaluate(facts(payee_is_new=True), p).tier == 0


def test_naive_timestamp_is_refused(policy):
    with pytest.raises(ValueError):
        evaluate(facts(created_at=datetime(2026, 11, 20, 12, 0)), policy)


# ---- policy validation: fail closed ----------------------------------------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["tier_thresholds_paise"].update(tier2="1"),
        lambda d: d.pop("rules"),
        lambda d: d.__setitem__("approval_matrix", [{"up_to_paise": "1", "approvers": ["a"]}]),
        lambda d: d["tier_thresholds_paise"].update(tier1="abc"),
    ],
)
def test_bad_policy_is_refused(mutate):
    doc = contract_policy()
    mutate(doc)
    with pytest.raises(PolicyError):
        PolicyDocument.from_contract(doc)


# ---- approval matrix ---------------------------------------------------------------


def test_matrix_up_to_25_lakh_goes_to_cfo(policy):
    assert approvers_for(25 * LAKH, policy) == ("cfo@acme.example",)


def test_matrix_above_25_lakh_needs_cfo_and_md(policy):
    assert approvers_for(25 * LAKH + 1, policy) == ("cfo@acme.example", "md@acme.example")


# ---- money ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["0", "-5", "1.5", "007", "", "1e9", "١٢٣"])
def test_parse_paise_rejects(bad):
    with pytest.raises(ValueError):
        parse_paise(bad)


def test_money_formatting():
    assert parse_paise("465000000") == 465000000
    assert indian_grouping(4650000) == "46,50,000"
    assert rupees_text(50000000) == "Rupees 5,00,000"
    assert threshold_label(10_000_000_000) == "10_crore"
