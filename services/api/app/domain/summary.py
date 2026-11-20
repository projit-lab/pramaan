"""The payment summary an approver signs, built only from stored payment facts.

One function so the approval endpoint, the batch endpoint and the payment gate
can never drift apart: the gate's tamper check recomputes exactly these fields
from the payment as it stands now.
"""

from __future__ import annotations

from typing import Any


def payment_summary_fields(intent: Any, nonce: str, expires_at: str) -> dict[str, str]:
    return {
        "amount_paise": str(intent.amount_paise),
        "currency": str(intent.currency or "INR"),
        "expires_at": expires_at or "",
        "initiator": f"{intent.initiator_type}:{intent.initiator_id}",
        "intent_id": intent.intent_id,
        "invoice_sha256": intent.invoice_sha256 or "",
        "nonce": nonce,
        "payee_account": intent.payee_account or intent.payee_account_last4,
        "payee_ifsc": intent.payee_ifsc,
        "payee_name": intent.payee_name,
        "payer_account": intent.payer_account,
        "purpose": intent.purpose or "",
        "v": "1",
    }
