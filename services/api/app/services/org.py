"""Loading the M2+ organisation tree and the approvers from the database into the
engine's plain objects, and saving a node after the tighten-only check."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Approver, Delegation, OrgNode, OrgRule
from app.domain.approver_levels import Person, can_delegate
from app.domain.hierarchy import Node, Rule, validate_tighten_only
from app.domain.ids import new_id
from app.errors import ProblemException


def load_tree(s: Session) -> dict[str, Node]:
    rules: dict[str, list[Rule]] = {}
    for r in s.scalars(select(OrgRule).order_by(OrgRule.code)):
        rules.setdefault(r.node_id, []).append(
            Rule(r.rule_id, r.code, r.text, r.expression, r.min_tier, r.hard_flag, r.enabled)
        )
    return {
        n.node_id: Node(
            n.node_id,
            n.kind,
            n.name,
            n.parent_id,
            n.settings or {},
            tuple(rules.get(n.node_id, ())),
        )
        for n in s.scalars(select(OrgNode))
    }


def load_people(s: Session, company_id: str) -> list[Person]:
    return [
        Person(a.email, a.level, a.node_id)
        for a in s.scalars(
            select(Approver).where(
                Approver.company_id == company_id,
                Approver.active.is_(True),
                Approver.level.is_not(None),
            )
        )
    ]


def active_delegates(s: Session, email: str, now: datetime) -> list[str]:
    rows = s.scalars(select(Delegation).where(Delegation.delegator_email == email))
    out = []
    for d in rows:
        start = d.valid_from if d.valid_from.tzinfo else d.valid_from.replace(tzinfo=timezone.utc)
        end = d.valid_to if d.valid_to.tzinfo else d.valid_to.replace(tzinfo=timezone.utc)
        if start <= now < end:
            out.append(d.delegate_email)
    return out


def tree_view(nodes: dict[str, Node]) -> list[dict[str, Any]]:
    """Every node with its own rules, plus the codes it inherits (shown greyed in
    the policy editor)."""
    out = []
    for node in sorted(nodes.values(), key=lambda n: (_depth(n, nodes), n.name)):
        inherited, current = [], node.parent_id
        while current:
            parent = nodes[current]
            inherited = [r.code for r in parent.rules if r.enabled] + inherited
            current = parent.parent_id
        out.append(
            {
                "node_id": node.node_id,
                "parent_id": node.parent_id,
                "kind": node.kind,
                "name": node.name,
                "settings": node.settings,
                "rules": [
                    {
                        "rule_id": r.rule_id,
                        "code": r.code,
                        "text": r.text,
                        "expression": r.expression,
                        "min_tier": r.min_tier,
                        "hard_flag": r.hard_flag,
                        "enabled": r.enabled,
                    }
                    for r in node.rules
                ],
                "inherited_rule_codes": inherited,
            }
        )
    return out


def _depth(node: Node, nodes: dict[str, Node]) -> int:
    d, current = 0, node.parent_id
    while current:
        d, current = d + 1, nodes[current].parent_id
    return d


def save_node(
    s: Session, node_id: str, body: Any, base: dict[str, Any], company_id: str, now: datetime
) -> list[str]:
    """Create or replace one node's settings and rules. Returns the problems found
    by the tighten-only check; nothing is written when there are any."""
    nodes = load_tree(s)
    existing = nodes.get(node_id)
    parent_id = body.parent_id if existing is None else existing.parent_id
    kind = body.kind if existing is None else existing.kind
    if existing is None and (not body.kind or not body.name):
        raise ProblemException(
            422, "New node needs kind and name", "Give kind, name and parent_id."
        )
    if parent_id is not None and parent_id not in nodes:
        raise ProblemException(422, "Unknown parent", f"No node {parent_id}.")
    candidate = Node(
        node_id,
        kind,
        body.name or existing.name,
        parent_id,
        body.settings or {},
        tuple(
            Rule(
                r.rule_id or new_id("rl"),
                r.code,
                r.text,
                r.expression,
                r.min_tier,
                r.hard_flag,
                r.enabled,
            )
            for r in body.rules
        ),
    )
    problems = validate_tighten_only(candidate, nodes, base)
    if problems:
        return problems
    row = s.get(OrgNode, node_id)
    if row is None:
        row = OrgNode(
            node_id=node_id,
            parent_id=parent_id,
            kind=kind,
            name=candidate.name,
            company_id=company_id if kind != "group" else None,
            settings={},
            created_at=now,
        )
        s.add(row)
    row.name = candidate.name
    row.settings = candidate.settings
    s.flush()
    for old in s.scalars(select(OrgRule).where(OrgRule.node_id == node_id)):
        s.delete(old)
    s.flush()
    for r in candidate.rules:
        s.add(
            OrgRule(
                rule_id=r.rule_id,
                node_id=node_id,
                code=r.code,
                text=r.text,
                expression=r.expression,
                min_tier=r.min_tier,
                hard_flag=r.hard_flag,
                enabled=r.enabled,
                created_at=now,
            )
        )
    return []


def check_delegation(s: Session, delegator: str, delegate: str) -> None:
    people = {
        a.email: a
        for a in s.scalars(select(Approver).where(Approver.email.in_([delegator, delegate])))
    }
    a, b = people.get(delegator), people.get(delegate)
    if a is None or b is None or a.level is None or b.level is None:
        raise ProblemException(
            422, "Unknown approver", "Both people must be approvers with a level."
        )
    if not can_delegate(Person(a.email, a.level, a.node_id), Person(b.email, b.level, b.node_id)):
        raise ProblemException(
            422, "Delegation refused", "Approvals can never be delegated to someone more junior."
        )
