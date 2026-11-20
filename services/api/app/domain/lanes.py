"""M2+ lane sorter and approval windows.

How payments are sorted (build plan, M2+). The first matching row wins, so
nothing slips into a lighter lane:

  1  any hard flag, or tier 2 or 3                          -> individual review
  2  known payee inside a valid standing mandate, no flags  -> auto-release, logged
  3  tier 0, known payee, no flags                          -> auto-release, logged
  4  tier 1, every check passed, no flags (new payees too)  -> batch at the next window
     anything else                                          -> individual review

Hard flags: bank details changed in 30 days, failed name check or look-alike,
invoice mismatch, pressure language or a chat instruction, a Model Armor finding,
an unusual amount, and any hierarchy rule marked hard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_WINDOWS = ("11:00", "16:00")

INDIVIDUAL = "individual"
BATCH = "batch"
AUTO_RELEASE = "auto_release"

# v1 reason codes that are hard flags in M2+.
HARD_REASON_CODES = frozenset({"bank_details_changed", "instruction_by_chat"})


@dataclass(frozen=True)
class LaneInput:
    tier: int
    payee_known: bool
    reason_codes: tuple[str, ...]
    checks_passed: bool
    name_check: str
    look_alike: bool
    invoice_match: str
    unusual_amount: bool
    standing_mandate_ok: bool
    hierarchy_hard_flags: tuple[str, ...] = ()
    pressure_language: bool = False
    model_armor_finding: bool = False


@dataclass(frozen=True)
class LaneResult:
    lane: str
    row: int
    hard_flags: tuple[str, ...]
    why: str


def hard_flags(x: LaneInput) -> tuple[str, ...]:
    flags = [c for c in x.reason_codes if c in HARD_REASON_CODES]
    if x.name_check != "match":
        flags.append(f"name_check_{x.name_check}")
    if x.look_alike:
        flags.append("look_alike")
    if x.invoice_match == "mismatch":
        flags.append("invoice_mismatch")
    if x.pressure_language:
        flags.append("pressure_language")
    if x.model_armor_finding:
        flags.append("model_armor_finding")
    if x.unusual_amount:
        flags.append("unusual_amount")
    flags.extend(x.hierarchy_hard_flags)
    return tuple(dict.fromkeys(flags))


def sort_lane(x: LaneInput) -> LaneResult:
    flags = hard_flags(x)
    if flags or x.tier >= 2:
        why = f"hard flags: {', '.join(flags)}" if flags else f"tier {x.tier}"
        return LaneResult(INDIVIDUAL, 1, flags, why)
    if x.payee_known and x.standing_mandate_ok:
        return LaneResult(AUTO_RELEASE, 2, flags, "known payee inside a valid standing mandate")
    if x.tier == 0 and x.payee_known:
        return LaneResult(AUTO_RELEASE, 3, flags, "tier 0 to a known payee")
    if x.tier == 1 and x.checks_passed:
        return LaneResult(BATCH, 4, flags, "tier 1 and every check passed")
    return LaneResult(INDIVIDUAL, 5, flags, "did not qualify for a lighter lane")


def next_window(now: datetime, windows: tuple[str, ...] | list[str] = DEFAULT_WINDOWS) -> datetime:
    """The first approval window strictly after `now`, in IST, returned in UTC."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(IST)
    times = sorted(time.fromisoformat(w) for w in windows)
    if not times:
        raise ValueError("at least one approval window is needed")
    for day in (0, 1):
        date = (local + timedelta(days=day)).date()
        for t in times:
            candidate = datetime.combine(date, t, IST)
            if candidate > local:
                return candidate.astimezone(timezone.utc)
    raise AssertionError("unreachable")


def unusual_amount(
    amount_paise: int, paid_amounts: list[int], factor: int = 3, min_history: int = 3
) -> bool:
    """More than `factor` times the largest earlier payment to this payee, once
    there are at least `min_history` earlier payments to judge by."""
    if len(paid_amounts) < min_history:
        return False
    return amount_paise > factor * max(paid_amounts)
