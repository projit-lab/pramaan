"""Sandbox Payout Adapter (M2, Prajit).

Records payout to Firestore collection 'payouts' when a payment is released by the gate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.runtime import Runtime


class SandboxPayout:
    """Records payouts to the read model (Firestore collection 'payouts')."""

    def __init__(self, rt: Runtime):
        self.rt = rt

    def record_payout(
        self,
        payout_id: str,
        mandate_id: str,
        intent_id: str,
        amount_paise: str,
        currency: str,
        payee_name_at_bank: str,
        payee_account_last4: str,
        payee_ifsc: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        payout_data = {
            "payoutId": payout_id,
            "mandateId": mandate_id,
            "intentId": intent_id,
            "amountPaise": amount_paise,
            "currency": currency,
            "payeeNameAtBank": payee_name_at_bank,
            "payeeAccountLast4": payee_account_last4,
            "payeeIfsc": payee_ifsc,
            "status": "paid",
            "createdAt": created_at,
        }
        self.rt.read_model.set_document("payouts", payout_id, payout_data)
        return payout_data
