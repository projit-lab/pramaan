"""M2+ hierarchy engine (Danish; Prajit reviews before merge).

The organisation tree is group > company > plant > department. Every node can
hold rules written in CEL (the expression language Google Cloud IAM Conditions
use) over the payment's attributes, and settings that may only tighten what the
parent allows.

Evaluation walks from the root to the payment's department, evaluates every
enabled rule, and takes the strictest result: the highest minimum tier, and the
union of hard flags. Because every ancestor's rules always run, a child can add
strictness but never remove it. The settings that could loosen something are
checked separately (validate_tighten_only) and a loosening edit is rejected with
the reason, before it is ever stored.

Every decision records which rule fired and where in the tree it lives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from functools import lru_cache
from typing import Any

import celpy

KINDS = ("group", "company", "plant", "department")

# Settings a node may set, and which direction is stricter.
LOWER_IS_STRICTER = ("tier1_paise", "tier2_paise", "tier3_paise", "auto_release_cap_paise")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    code: str
    text: str
    expression: str
    min_tier: int
    hard_flag: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    name: str
    parent_id: str | None
    settings: dict[str, Any] = field(default_factory=dict)
    rules: tuple[Rule, ...] = ()


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    code: str
    text: str
    min_tier: int
    hard_flag: bool
    path: tuple[str, ...]  # node names from the root to the node that holds the rule

    def as_trace(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "code": self.code,
            "text": self.text,
            "min_tier": self.min_tier,
            "hard_flag": self.hard_flag,
            "path": " > ".join(self.path),
        }


@dataclass(frozen=True)
class HierarchyResult:
    tier_floor: int
    hard_flags: tuple[str, ...]
    hits: tuple[RuleHit, ...]
    effective: dict[str, Any]


class RuleError(ValueError):
    pass


# ---- CEL ---------------------------------------------------------------------------


_ENV = celpy.Environment()


@lru_cache(maxsize=512)
def compile_rule(expression: str):
    try:
        return _ENV.program(_ENV.compile(expression))
    except Exception as e:  # parse or type error
        raise RuleError(f"not a valid CEL expression: {e}") from e


def _truthy(value: Any) -> bool:
    if isinstance(value, celpy.celtypes.BoolType) or isinstance(value, bool):
        return bool(value)
    raise RuleError("a rule must evaluate to true or false")


def matches(expression: str, attributes: dict[str, Any]) -> bool:
    program = compile_rule(expression)
    try:
        result = program.evaluate({"payment": celpy.json_to_cel(attributes)})
    except Exception as e:
        raise RuleError(f"rule failed on this payment: {e}") from e
    if isinstance(result, celpy.CELEvalError):
        raise RuleError(f"rule failed on this payment: {result}")
    return _truthy(result)


# ---- the path and the effective settings --------------------------------------------


def path_to(node_id: str, nodes: dict[str, Node]) -> list[Node]:
    """Root first, ending at node_id. Refuses cycles and unknown nodes."""
    path: list[Node] = []
    seen: set[str] = set()
    current: str | None = node_id
    while current is not None:
        if current in seen:
            raise RuleError(f"the organisation tree has a cycle at {current}")
        if current not in nodes:
            raise RuleError(f"unknown organisation node {current}")
        seen.add(current)
        node = nodes[current]
        path.append(node)
        current = node.parent_id
    return list(reversed(path))


def _hours(value: dict[str, str] | None) -> tuple[time, time] | None:
    if not value:
        return None
    return time.fromisoformat(value["start"]), time.fromisoformat(value["end"])


def effective_settings(path: list[Node], base: dict[str, Any]) -> dict[str, Any]:
    """Fold the settings down the path. Thresholds take the lowest value, working
    hours the narrowest window, approval windows the latest node that sets them."""
    out = dict(base)
    for node in path:
        s = node.settings or {}
        for key in LOWER_IS_STRICTER:
            if key in s and s[key] is not None:
                value = int(s[key])
                out[key] = value if out.get(key) is None else min(int(out[key]), value)
        hours = _hours(s.get("working_hours_ist"))
        if hours:
            cur = _hours(out.get("working_hours_ist"))
            start, end = hours if cur is None else (max(cur[0], hours[0]), min(cur[1], hours[1]))
            out["working_hours_ist"] = {
                "start": start.isoformat(timespec="minutes"),
                "end": end.isoformat(timespec="minutes"),
            }
        if s.get("approval_windows_ist"):
            out["approval_windows_ist"] = list(s["approval_windows_ist"])
    return out


# ---- evaluation ----------------------------------------------------------------------


def evaluate_hierarchy(
    department_id: str, nodes: dict[str, Node], attributes: dict[str, Any], base: dict[str, Any]
) -> HierarchyResult:
    path = path_to(department_id, nodes)
    names: list[str] = []
    hits: list[RuleHit] = []
    for node in path:
        names.append(node.name)
        for rule in node.rules:
            if not rule.enabled:
                continue
            try:
                fired = matches(rule.expression, attributes)
            except RuleError:
                # Fail closed: a rule that cannot be evaluated sends the payment to a
                # person, and the trace says which rule and why.
                hits.append(
                    RuleHit(
                        rule.rule_id,
                        f"{rule.code}_error",
                        f"Rule {rule.code} could not be evaluated, so a person must review.",
                        max(1, rule.min_tier),
                        True,
                        tuple(names),
                    )
                )
                continue
            if fired:
                hits.append(
                    RuleHit(
                        rule.rule_id,
                        rule.code,
                        rule.text,
                        rule.min_tier,
                        rule.hard_flag,
                        tuple(names),
                    )
                )
    floor = max((h.min_tier for h in hits), default=0)
    flags = tuple(dict.fromkeys(h.code for h in hits if h.hard_flag))
    return HierarchyResult(floor, flags, tuple(hits), effective_settings(path, base))


# ---- tighten-only --------------------------------------------------------------------


def validate_tighten_only(node: Node, nodes: dict[str, Node], base: dict[str, Any]) -> list[str]:
    """Reasons this node would loosen what its ancestors allow. Empty means it
    only tightens. Run before a node's settings or rules are saved."""
    problems: list[str] = []
    if node.kind not in KINDS:
        problems.append(f"kind must be one of {', '.join(KINDS)}")
    parent_path = path_to(node.parent_id, nodes) if node.parent_id else []
    if parent_path:
        expected = KINDS.index(parent_path[-1].kind) + 1
        if expected >= len(KINDS):
            problems.append(
                f"a {parent_path[-1].kind} is the last level and cannot contain anything"
            )
        elif node.kind != KINDS[expected]:
            problems.append(f"a {parent_path[-1].kind} can only contain a {KINDS[expected]}")
    elif node.kind != "group":
        problems.append("only a group can sit at the top of the tree")
    inherited = effective_settings(parent_path, base)
    s = node.settings or {}

    for key in LOWER_IS_STRICTER:
        if key in s and s[key] is not None and inherited.get(key) is not None:
            if int(s[key]) > int(inherited[key]):
                problems.append(f"{key} {s[key]} is looser than the {inherited[key]} it inherits")
    t = [s.get(k, inherited.get(k)) for k in ("tier1_paise", "tier2_paise", "tier3_paise")]
    if all(v is not None for v in t) and not (int(t[0]) < int(t[1]) < int(t[2])):
        problems.append("tier thresholds must rise: tier1 < tier2 < tier3")

    hours = _hours(s.get("working_hours_ist"))
    parent_hours = _hours(inherited.get("working_hours_ist"))
    if hours and parent_hours and (hours[0] < parent_hours[0] or hours[1] > parent_hours[1]):
        problems.append("working hours are wider than the hours this node inherits")
    if hours and not hours[0] < hours[1]:
        problems.append("working hours must start before they end")

    ancestor_codes = {r.code: r for n in parent_path for r in n.rules if r.enabled}
    for rule in node.rules:
        try:
            compile_rule(rule.expression)
        except RuleError as e:
            problems.append(f"rule {rule.code}: {e}")
        if not 0 <= rule.min_tier <= 3:
            problems.append(f"rule {rule.code}: min_tier must be 0 to 3")
        parent_rule = ancestor_codes.get(rule.code)
        if parent_rule is not None:
            if not rule.enabled:
                problems.append(
                    f"rule {rule.code} is set by a parent and cannot be switched off here"
                )
            elif rule.min_tier < parent_rule.min_tier:
                problems.append(
                    f"rule {rule.code} asks for tier {rule.min_tier}, "
                    f"below the parent's {parent_rule.min_tier}"
                )
            elif parent_rule.hard_flag and not rule.hard_flag:
                problems.append(f"rule {rule.code} drops the parent's hard flag")
    return problems
