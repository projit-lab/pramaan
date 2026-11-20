"""M2+ engine, pure parts: hierarchy evaluation, tighten-only, payee checks, lane
order, approval windows, approver levels. The plan asks for tests of tier
boundaries, lane order and tighten-only rejection; those are marked below."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.approver_levels import (
    AP_MANAGER,
    CFO,
    CONTROLLER,
    MD,
    Person,
    can_delegate,
    escalate_to,
    required_levels,
    route,
)
from app.domain.hierarchy import (
    Node,
    Rule,
    RuleError,
    effective_settings,
    evaluate_hierarchy,
    matches,
    path_to,
    validate_tighten_only,
)
from app.domain.lanes import (
    AUTO_RELEASE,
    BATCH,
    INDIVIDUAL,
    LaneInput,
    next_window,
    sort_lane,
    unusual_amount,
)
from app.domain.payee_checks import invoice_match, look_alike, name_check, similarity

IST = timezone(timedelta(hours=5, minutes=30))
LAKH = 100_000 * 100
BASE = {
    "tier1_paise": 5 * LAKH,
    "tier2_paise": 25 * LAKH,
    "tier3_paise": 1000 * LAKH,
    "working_hours_ist": {"start": "09:00", "end": "19:00"},
}


def tree(**overrides) -> dict[str, Node]:
    nodes = {
        "grp": Node(
            "grp",
            "group",
            "Acme Group",
            None,
            {},
            (
                Rule(
                    "r_big",
                    "big_payment",
                    "Above Rs 50 lakh.",
                    "payment.amount_paise > 500000000",
                    2,
                ),
            ),
        ),
        "co": Node("co", "company", "Acme Engineering", "grp", {}, ()),
        "plant": Node("plant", "plant", "Chennai plant", "co", {"tier1_paise": 2 * LAKH}, ()),
        "ap": Node(
            "ap",
            "department",
            "Accounts payable",
            "plant",
            {},
            (
                Rule(
                    "r_new",
                    "new_payee_over_1_lakh",
                    "New payee above Rs 1 lakh.",
                    "payment.payee.is_new && payment.amount_paise > 10000000",
                    1,
                    True,
                ),
            ),
        ),
    }
    nodes.update(overrides)
    return nodes


def attrs(**kw):
    a = {
        "amount_paise": 50 * LAKH,
        "channel": "portal",
        "initiator_type": "human",
        "payee": {"is_new": False, "vendor_id": "vd_x", "months_of_history": 12},
    }
    a.update(kw)
    return a


# ---- CEL and the path ---------------------------------------------------------------


def test_cel_rule_matches_payment_attributes():
    assert matches("payment.amount_paise > 100 && payment.channel == 'portal'", attrs())
    assert not matches("payment.payee.is_new", attrs())


def test_bad_cel_is_refused():
    with pytest.raises(RuleError):
        matches("payment.amount_paise >", attrs())
    with pytest.raises(RuleError):
        matches("payment.amount_paise + 1", attrs())  # not a true/false


def test_path_runs_root_to_department():
    assert [n.node_id for n in path_to("ap", tree())] == ["grp", "co", "plant", "ap"]


def test_cycle_and_unknown_nodes_are_refused():
    nodes = tree(grp=Node("grp", "group", "G", "ap"))
    with pytest.raises(RuleError):
        path_to("ap", nodes)
    with pytest.raises(RuleError):
        path_to("nope", tree())


# ---- hierarchy evaluation: strictest wins, trace records the path ----------------------


def test_strictest_rule_wins_and_trace_has_the_path():
    r = evaluate_hierarchy(
        "ap",
        tree(),
        attrs(
            amount_paise=600 * LAKH,
            payee={"is_new": True, "vendor_id": None, "months_of_history": 0},
        ),
        BASE,
    )
    assert r.tier_floor == 2
    assert [h.code for h in r.hits] == ["big_payment", "new_payee_over_1_lakh"]
    assert r.hits[0].as_trace()["path"] == "Acme Group"
    assert (
        r.hits[1].as_trace()["path"]
        == "Acme Group > Acme Engineering > Chennai plant > Accounts payable"
    )
    assert r.hard_flags == ("new_payee_over_1_lakh",)


def test_no_rule_fires_floor_is_zero():
    r = evaluate_hierarchy("ap", tree(), attrs(amount_paise=LAKH), BASE)
    assert (r.tier_floor, r.hits, r.hard_flags) == (0, (), ())


def test_settings_tighten_down_the_path():
    eff = evaluate_hierarchy("ap", tree(), attrs(), BASE).effective
    assert eff["tier1_paise"] == 2 * LAKH  # plant lowered it
    assert eff["tier2_paise"] == 25 * LAKH


def test_rule_that_breaks_on_a_payment_fails_closed():
    broken = Node(
        "ap",
        "department",
        "AP",
        "plant",
        {},
        (Rule("r_b", "needs_field", "x", "payment.missing_field > 1", 0),),
    )
    r = evaluate_hierarchy("ap", tree(ap=broken), attrs(), BASE)
    assert r.tier_floor >= 1 and r.hard_flags == ("needs_field_error",)


def test_disabled_rule_does_not_fire():
    off = Node(
        "ap",
        "department",
        "AP",
        "plant",
        {},
        (Rule("r_new", "always", "x", "true", 3, True, enabled=False),),
    )
    assert evaluate_hierarchy("ap", tree(ap=off), attrs(), BASE).tier_floor == 0


def test_working_hours_take_the_narrowest_window():
    path = [
        Node("a", "group", "A", None, {"working_hours_ist": {"start": "08:00", "end": "20:00"}}),
        Node("b", "company", "B", "a", {"working_hours_ist": {"start": "10:00", "end": "21:00"}}),
    ]
    assert effective_settings(path, BASE)["working_hours_ist"] == {"start": "10:00", "end": "19:00"}


# ---- tighten-only rejection (plan: tests required) -----------------------------------------


def test_tighter_child_is_accepted():
    child = Node(
        "d2",
        "department",
        "Treasury",
        "plant",
        {"tier1_paise": LAKH},
        (Rule("r1", "big_payment", "x", "payment.amount_paise > 100000000", 3),),
    )
    assert validate_tighten_only(child, tree(), BASE) == []


def test_raising_a_threshold_is_rejected():
    child = Node("d2", "department", "Treasury", "plant", {"tier1_paise": 3 * LAKH}, ())
    problems = validate_tighten_only(child, tree(), BASE)
    assert any("tier1_paise" in p and "looser" in p for p in problems)


def test_switching_off_a_parents_rule_is_rejected():
    child = Node(
        "d2",
        "department",
        "Treasury",
        "plant",
        {},
        (Rule("r1", "big_payment", "x", "payment.amount_paise > 500000000", 2, enabled=False),),
    )
    assert any("cannot be switched off" in p for p in validate_tighten_only(child, tree(), BASE))


def test_lowering_a_parents_rule_tier_is_rejected():
    child = Node(
        "d2",
        "department",
        "Treasury",
        "plant",
        {},
        (Rule("r1", "big_payment", "x", "payment.amount_paise > 500000000", 1),),
    )
    assert any("below the parent's 2" in p for p in validate_tighten_only(child, tree(), BASE))


def test_dropping_a_parents_hard_flag_is_rejected():
    nodes = tree()
    grandchild = Node("t", "department", "T", "plant", {}, ())
    nodes["t"] = grandchild
    parent_hard = Node("ap", "department", "AP", "plant", {}, ())
    child = Node(
        "x",
        "department",
        "X",
        "plant",
        {},
        (Rule("r", "big_payment", "x", "payment.amount_paise > 500000000", 2, hard_flag=False),),
    )
    nodes["grp"] = Node(
        "grp",
        "group",
        "Acme Group",
        None,
        {},
        (Rule("r_big", "big_payment", "x", "payment.amount_paise > 500000000", 2, hard_flag=True),),
    )
    assert parent_hard and any("hard flag" in p for p in validate_tighten_only(child, nodes, BASE))


def test_wider_working_hours_are_rejected():
    child = Node(
        "d2", "department", "T", "plant", {"working_hours_ist": {"start": "07:00", "end": "19:00"}}
    )
    assert any("wider" in p for p in validate_tighten_only(child, tree(), BASE))


def test_invalid_cel_and_wrong_kind_are_rejected():
    child = Node("d2", "plant", "T", "plant", {}, (Rule("r", "x", "x", "payment >", 1),))
    problems = validate_tighten_only(child, tree(), BASE)
    assert any("valid CEL" in p for p in problems)
    assert any("can only contain a department" in p for p in problems)


# ---- payee checks ----------------------------------------------------------------------------


def test_name_check():
    assert name_check("Sri Lakshmi Castings", "SRI LAKSHMI CASTINGS PVT LTD") == "match"
    assert name_check("Global Trade Solutions", "Ramesh Kumar") == "mismatch"
    assert name_check("Anyone", None) == "not_found"


def test_look_alike_flags_the_newcomer_only():
    established = [
        ("vd_sri_lakshmi", "Sri Lakshmi Castings"),
        ("vd_kaveri", "Kaveri Steel Traders"),
    ]
    hit, of, score = look_alike("Sri Laxmi Castings", "vd_sri_laxmi", established)
    assert hit and of == "vd_sri_lakshmi" and score >= 0.8
    assert similarity("Sri Laxmi Castings", "Sri Lakshmi Castings") > 0.9
    hit, _, _ = look_alike(
        "Sri Lakshmi Castings", "vd_sri_lakshmi", [("vd_kaveri", "Kaveri Steel Traders")]
    )
    assert not hit


def test_one_off_payee_with_an_existing_vendors_exact_name_is_a_look_alike():
    hit, of, score = look_alike(
        "Kaveri Steel Traders", None, [("vd_kaveri", "Kaveri Steel Traders")]
    )
    assert hit and of == "vd_kaveri" and score == 1.0


def test_invoice_match():
    vendor = {"account_last4": "7781", "ifsc": "ABCD0123456", "gstin": "33AABCS1429P1Z5"}
    assert invoice_match(None, vendor, 100) == ("unknown", ())
    assert invoice_match({"account_last4": "7781", "amount_paise": "100"}, vendor, 100) == (
        "match",
        (),
    )
    assert invoice_match({"account_last4": "9032", "amount_paise": "100"}, vendor, 100) == (
        "mismatch",
        ("account_last4",),
    )


# ---- lane order (plan: tests required) ---------------------------------------------------------


def lane(**kw):
    base = dict(
        tier=1,
        payee_known=True,
        reason_codes=(),
        checks_passed=True,
        name_check="match",
        look_alike=False,
        invoice_match="unknown",
        unusual_amount=False,
        standing_mandate_ok=False,
    )
    base.update(kw)
    return sort_lane(LaneInput(**base))


@pytest.mark.parametrize(
    "kw,expected_lane,row",
    [
        ({"tier": 2}, INDIVIDUAL, 1),
        ({"tier": 3, "standing_mandate_ok": True}, INDIVIDUAL, 1),
        ({"reason_codes": ("bank_details_changed",), "standing_mandate_ok": True}, INDIVIDUAL, 1),
        ({"reason_codes": ("instruction_by_chat",)}, INDIVIDUAL, 1),
        ({"name_check": "mismatch", "checks_passed": False}, INDIVIDUAL, 1),
        ({"look_alike": True, "checks_passed": False}, INDIVIDUAL, 1),
        ({"invoice_match": "mismatch", "checks_passed": False}, INDIVIDUAL, 1),
        ({"unusual_amount": True}, INDIVIDUAL, 1),
        ({"hierarchy_hard_flags": ("new_payee_over_1_lakh",)}, INDIVIDUAL, 1),
        ({"pressure_language": True}, INDIVIDUAL, 1),
        ({"model_armor_finding": True}, INDIVIDUAL, 1),
        ({"standing_mandate_ok": True}, AUTO_RELEASE, 2),
        ({"tier": 0}, AUTO_RELEASE, 3),
        ({"tier": 1}, BATCH, 4),
        ({"tier": 1, "payee_known": False}, BATCH, 4),  # new payees included
        # No row covers tier 0 to an unknown payee (row 3 needs a known payee,
        # row 4 needs tier 1), so it falls through to a person.
        ({"tier": 0, "payee_known": False}, INDIVIDUAL, 5),
    ],
)
def test_lane_order_first_match_wins(kw, expected_lane, row):
    r = lane(**kw)
    assert (r.lane, r.row) == (expected_lane, row), r.why


def test_new_payee_never_uses_a_standing_mandate():
    assert lane(payee_known=False, standing_mandate_ok=True).lane == BATCH


# ---- tier boundaries for approvers (plan: tests required) ----------------------------------------


@pytest.mark.parametrize(
    "tier,levels", [(0, ()), (1, (AP_MANAGER,)), (2, (CONTROLLER,)), (3, (CFO, MD))]
)
def test_required_levels_per_tier(tier, levels):
    assert required_levels(tier) == levels


PEOPLE = [
    Person("ap.mgr@acme.example", AP_MANAGER, "ap"),
    Person("controller@acme.example", CONTROLLER, "plant"),
    Person("cfo@acme.example", CFO, "co"),
    Person("md@acme.example", MD, "grp"),
]
PATH = ["grp", "co", "plant", "ap"]


def test_routing_picks_the_nearest_qualified_person():
    assert [p.email for p in route(PATH, PEOPLE, 1)] == ["ap.mgr@acme.example"]
    assert [p.email for p in route(PATH, PEOPLE, 2)] == ["controller@acme.example"]
    assert [p.email for p in route(PATH, PEOPLE, 3)] == ["cfo@acme.example", "md@acme.example"]
    assert route(PATH, PEOPLE, 0) == []


def test_routing_never_waits_for_someone_who_does_not_exist():
    with pytest.raises(LookupError):
        route(PATH, [p for p in PEOPLE if p.level != MD], 3)


def test_escalation_goes_upward_only():
    up = escalate_to(PEOPLE[0], PATH, PEOPLE, {"ap.mgr@acme.example"})
    assert up.email == "controller@acme.example"
    assert escalate_to(PEOPLE[3], PATH, PEOPLE, set()) is None


def test_delegation_never_to_someone_more_junior():
    assert can_delegate(PEOPLE[1], PEOPLE[2])  # Controller -> CFO
    assert can_delegate(PEOPLE[2], Person("cfo2@acme.example", CFO, "co"))
    assert not can_delegate(PEOPLE[2], PEOPLE[0])  # CFO -> AP Manager


# ---- approval windows and unusual amounts --------------------------------------------------------


@pytest.mark.parametrize(
    "now_ist,window_ist",
    [
        ((9, 0), (2026, 11, 20, 11, 0)),
        ((11, 0), (2026, 11, 20, 16, 0)),  # strictly after
        ((15, 59), (2026, 11, 20, 16, 0)),
        ((21, 0), (2026, 11, 21, 11, 0)),
    ],
)
def test_next_window(now_ist, window_ist):
    now = datetime(2026, 11, 20, *now_ist, tzinfo=IST)
    assert next_window(now) == datetime(*window_ist, tzinfo=IST)


def test_unusual_amount_needs_history():
    assert not unusual_amount(10 * LAKH, [LAKH, LAKH])
    assert unusual_amount(10 * LAKH, [LAKH, 2 * LAKH, 3 * LAKH])
    assert not unusual_amount(9 * LAKH, [LAKH, 2 * LAKH, 3 * LAKH])
