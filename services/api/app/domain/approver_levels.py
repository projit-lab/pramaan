"""M2+ approver hierarchy.

Minimum level per tier: Tier 1 AP Manager or above, Tier 2 Controller or above,
Tier 3 the CFO plus the MD. Routing picks the nearest qualified approver walking
up from the payment's department; on timeout an approval escalates to the next
more senior approver; delegation never goes to someone more junior.
"""

from __future__ import annotations

from dataclasses import dataclass

AP_MANAGER, CONTROLLER, CFO, MD = 1, 2, 3, 4
LEVEL_NAMES = {AP_MANAGER: "AP Manager", CONTROLLER: "Controller", CFO: "CFO", MD: "MD"}
ROLE_LEVELS = {v: k for k, v in LEVEL_NAMES.items()}


@dataclass(frozen=True)
class Person:
    email: str
    level: int
    node_id: str | None  # where in the tree they sit; None means company-wide


def required_levels(tier: int) -> tuple[int, ...]:
    """Each entry is one approval that is needed, at that level or above. Tier 3
    needs two people, the CFO and the MD, in sequence (the sequence is M5)."""
    if tier <= 0:
        return ()
    if tier == 1:
        return (AP_MANAGER,)
    if tier == 2:
        return (CONTROLLER,)
    return (CFO, MD)


def route(path_ids: list[str], people: list[Person], tier: int) -> list[Person]:
    """Pick the approvers for a tier. Walk from the department up to the root and
    take, for each required level, the least senior qualified person nearest the
    department. Tier 3 needs exactly a CFO and an MD. Raises if nobody qualifies:
    a payment must never wait for an approver who does not exist."""
    chosen: list[Person] = []
    for needed in required_levels(tier):
        exact = tier >= 3  # Tier 3: the CFO *and* the MD, not two people above Controller
        pick = None
        for node_id in [*reversed(path_ids), None]:
            here = [
                p
                for p in people
                if p.node_id == node_id
                and p not in chosen
                and (p.level == needed if exact else p.level >= needed)
            ]
            if here:
                pick = min(here, key=lambda p: (p.level, p.email))
                break
        if pick is None:
            raise LookupError(f"no {LEVEL_NAMES[needed]} or above is set up for this department")
        chosen.append(pick)
    return chosen


def escalate_to(
    current: Person, path_ids: list[str], people: list[Person], already: set[str]
) -> Person | None:
    """The next more senior approver for this department, skipping anyone already
    asked. None when there is nobody above."""
    candidates = [
        p
        for p in people
        if p.level > current.level
        and p.email not in already
        and (p.node_id is None or p.node_id in path_ids)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (p.level, -_depth(p, path_ids), p.email))


def _depth(p: Person, path_ids: list[str]) -> int:
    return path_ids.index(p.node_id) if p.node_id in path_ids else -1


def can_delegate(delegator: Person, delegate: Person) -> bool:
    """Delegation never goes to someone more junior."""
    return delegate.level >= delegator.level and delegate.email != delegator.email
