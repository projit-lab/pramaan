"""The signed batch format (Prajit): one fingerprint approves a batch of Tier 1 lines.

What the phone signs is a small canonical summary of the batch, not each line:

    {"kind": "batch", "batch_id", "approver", "line_count", "total_paise",
     "lines_sha256", "nonce", "expires_at", "window_at", "v": "1"}

`lines_sha256` binds every line. Each line hash is the SHA-256 of that payment's
canonical summary (the same fields an individual approval signs, with the batch's
nonce and expiry), and lines_sha256 is the SHA-256 of the line hashes, lowercase
hex, sorted by intent id, joined with "\n".

At the gate, a line is released only if the payment as it stands now hashes to a
line hash in the batch, and those line hashes still hash to the lines_sha256 the
phone signed. Changing any line, or the stored list, breaks one of the two.

Tier 2 and 3 payments are never batched: the batch endpoints refuse them.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.domain.canonical import canonical_bytes
from app.domain.summary import payment_summary_fields

BATCH_KIND = "batch"
MAX_BATCH_TIER = 1


def line_hash(intent: Any, nonce: str, expires_at: str) -> str:
    fields = payment_summary_fields(intent, nonce, expires_at)
    return hashlib.sha256(canonical_bytes(fields)).hexdigest()


def lines_digest(line_hashes: list[str]) -> str:
    return hashlib.sha256("\n".join(line_hashes).encode("ascii")).hexdigest()


def batch_summary_fields(
    *,
    batch_id: str,
    approver: str,
    line_hashes: list[str],
    total_paise: int,
    nonce: str,
    expires_at: str,
    window_at: str,
) -> dict[str, str]:
    return {
        "kind": BATCH_KIND,
        "batch_id": batch_id,
        "approver": approver,
        "line_count": str(len(line_hashes)),
        "total_paise": str(total_paise),
        "lines_sha256": lines_digest(line_hashes),
        "nonce": nonce,
        "expires_at": expires_at,
        "window_at": window_at,
        "v": "1",
    }
