"""Money is an integer number of paise, sent as a string ("465000000" is Rs 46.5 lakh)."""

from __future__ import annotations

import re

_PAISE = re.compile(r"^[1-9][0-9]{0,17}$")

LAKH = 100_000 * 100  # paise
CRORE = 100 * LAKH


def parse_paise(value: str) -> int:
    """A positive integer of paise from its string form. No decimals, signs or
    leading zeros, so the same amount can never be written two ways."""
    if not isinstance(value, str) or not _PAISE.match(value):
        raise ValueError("amount_paise must be a positive whole number of paise, as a string")
    return int(value)


def indian_grouping(rupees: int) -> str:
    """1234567 -> '12,34,567'."""
    s = str(rupees)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def threshold_label(paise: int) -> str:
    """50000000 -> '5_lakh', 250000000 -> '25_lakh', 10000000000 -> '10_crore'.
    Used in reason codes such as amount_above_25_lakh."""
    if paise % CRORE == 0:
        return f"{paise // CRORE}_crore"
    if paise % LAKH == 0:
        return f"{paise // LAKH}_lakh"
    return f"{paise // 100}_rupees"


def rupees_text(paise: int) -> str:
    """50000000 -> 'Rupees 5,00,000'."""
    rupees, rem = divmod(paise, 100)
    text = f"Rupees {indian_grouping(rupees)}"
    return text if rem == 0 else f"{text}.{rem:02d}"
