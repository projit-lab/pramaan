"""M2+ automatic payee checks, run before any approver sees a payment. Each result
becomes an attribute the rules and the lane sorter read.

- name check: the name the (mock) bank holds for the account, against the payee
- look-alike: how close the payee's name is to a *different* known vendor
- invoice match: what Gemini read off the invoice (M3) against the vendor master

Name similarity is plain string similarity after removing what never tells
companies apart (case, punctuation, "pvt ltd" and friends), plus a few spelling
folds common in Indian names (laxmi / lakshmi).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

NAME_MATCH = 0.90
LOOK_ALIKE = 0.80

_NOISE = re.compile(
    r"\b(pvt|private|ltd|limited|llp|inc|co|company|corp|corporation|the|and|m/s|ms)\b"
)
_FOLDS = (("ksh", "x"), ("sh", "s"), ("aa", "a"), ("ee", "i"), ("oo", "u"), ("w", "v"), ("ph", "f"))


def normalise(name: str) -> str:
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _NOISE.sub(" ", s)
    return " ".join(s.split())


def fold(name: str) -> str:
    s = normalise(name)
    for a, b in _FOLDS:
        s = s.replace(a, b)
    return s


def similarity(a: str, b: str) -> float:
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    return max(
        SequenceMatcher(None, na, nb).ratio(), SequenceMatcher(None, fold(a), fold(b)).ratio()
    )


@dataclass(frozen=True)
class PayeeChecks:
    name_check: str  # match, mismatch, not_found
    bank_name: str | None
    look_alike: bool
    look_alike_of: str | None
    look_alike_score: float
    invoice_match: str  # match, mismatch, unknown
    invoice_mismatches: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return (
            self.name_check == "match" and not self.look_alike and self.invoice_match != "mismatch"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name_check": self.name_check,
            "bank_name": self.bank_name,
            "look_alike": self.look_alike,
            "look_alike_of": self.look_alike_of,
            "look_alike_score": round(self.look_alike_score, 3),
            "invoice_match": self.invoice_match,
            "invoice_mismatches": list(self.invoice_mismatches),
            "passed": self.passed,
        }


def name_check(payee_name: str, bank_name: str | None) -> str:
    if bank_name is None:
        return "not_found"
    return "match" if similarity(payee_name, bank_name) >= NAME_MATCH else "mismatch"


def look_alike(
    payee_name: str, payee_vendor_id: str | None, others: list[tuple[str, str]]
) -> tuple[bool, str | None, float]:
    """`others` is (vendor_id, legal_name) for the vendors the payee could be
    imitating: those established *before* the payee's vendor (all vendors, for a
    one-off payee). Comparing in that direction flags the newcomer "Sri Laxmi"
    and never the genuine, older "Sri Lakshmi"."""
    best_id, best = None, 0.0
    for vendor_id, legal_name in others:
        if vendor_id == payee_vendor_id:
            continue
        score = similarity(payee_name, legal_name)
        if score > best:
            best_id, best = vendor_id, score
    if normalise(payee_name) in {normalise(n) for v, n in others if v != payee_vendor_id}:
        return True, best_id, 1.0  # same name as another vendor: as suspicious as it gets
    return best >= LOOK_ALIKE, (best_id if best >= LOOK_ALIKE else None), best


def invoice_match(
    extraction: dict[str, Any] | None, vendor: dict[str, Any] | None, amount_paise: int
) -> tuple[str, tuple[str, ...]]:
    """`extraction` is M3's InvoiceExtraction fields (bank account last four, IFSC,
    GSTIN, amount). Unknown until M3 supplies one."""
    if not extraction or vendor is None:
        return "unknown", ()
    mismatches = []
    pairs = (
        ("account_last4", vendor.get("account_last4")),
        ("ifsc", vendor.get("ifsc")),
        ("gstin", vendor.get("gstin")),
    )
    for key, expected in pairs:
        got = extraction.get(key)
        if got and expected and str(got).upper() != str(expected).upper():
            mismatches.append(key)
    if extraction.get("amount_paise") and int(extraction["amount_paise"]) != amount_paise:
        mismatches.append("amount_paise")
    return ("mismatch" if mismatches else "match"), tuple(mismatches)
