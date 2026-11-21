"""Payment Gate Router (M2, Prajit).

POST /v1/gate/release: verify dual-signed mandate, detect tampering, atomically mark mandate used,
record sandbox payout, and publish payment.released.
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.adapters.payout import SandboxPayout
from app.adapters.signer import get_mandate_signer
from app.db.engine import unit_of_work
from app.db.models import Batch, Mandate, PaymentIntent
from app.domain.batch import BATCH_KIND, line_hash, lines_digest
from app.domain.canonical import canonical_bytes
from app.domain.ids import new_id
from app.domain.mandate import MandateInvalid, verify_mandate
from app.domain.models import AuthenticatedUser
from app.domain.summary import payment_summary_fields
from app.errors import ProblemException
from app.roles import require_roles
from app.runtime import Runtime, get_runtime, utc_now
from app.services.views import aware, ist

router = APIRouter(tags=["gate"])


class GateReleaseIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mandate_id: str = Field(pattern=r"^pm_[A-Za-z0-9]+$")
    idempotency_key: str | None = None


@router.post("/gate/release", operation_id="gateRelease")
def gate_release(
    body: GateReleaseIn,
    rt: Runtime = Depends(get_runtime),
    _user: AuthenticatedUser = Depends(require_roles("finance", "clerk", "service", "approver")),
) -> dict[str, Any]:
    """Release a payment only if its mandate signature and current payment facts match."""
    now = utc_now(rt)

    with unit_of_work(rt.sessions) as s:
        mandate = s.get(Mandate, body.mandate_id, with_for_update=True)
        if mandate is None:
            raise ProblemException(
                404, "Mandate not found", f"No mandate found with id '{body.mandate_id}'."
            )

        intent = s.get(PaymentIntent, mandate.intent_id, with_for_update=True)
        if intent is None:
            raise ProblemException(
                404, "Payment intent not found", "Intent associated with mandate missing."
            )

        # Single-use check: mandate releases one payment only
        if mandate.used_at is not None:
            rt.event_bus.publish(
                topic="payment-blocked",
                event_type="payment.blocked",
                company_id=rt.settings.COMPANY_ID,
                intent_id=intent.intent_id,
                actor={"type": "service", "id": "payment_gate"},
                data={
                    "reason": "mandate_already_used",
                    "detail": "This mandate has already been used to release a payment.",
                    "mandate_id": mandate.mandate_id,
                    "blocked_at_step": "verified",
                },
            )
            raise ProblemException(
                409,
                "Mandate already used",
                "A mandate releases one payment only and has already been used.",
                type_="https://pramaan.example/problems/mandate-already-used",
            )

        # Expiry check
        if aware(mandate.expires_at) <= now:
            rt.event_bus.publish(
                topic="payment-blocked",
                event_type="payment.blocked",
                company_id=rt.settings.COMPANY_ID,
                intent_id=intent.intent_id,
                actor={"type": "service", "id": "payment_gate"},
                data={
                    "reason": "mandate_expired",
                    "detail": "This mandate has expired.",
                    "mandate_id": mandate.mandate_id,
                    "blocked_at_step": "verified",
                },
            )
            raise ProblemException(
                409,
                "Mandate expired",
                "The mandate has expired.",
                type_="https://pramaan.example/problems/mandate-expired",
            )

        # Verify mandate with KMS public key
        signer = get_mandate_signer(rt.settings)
        kms_pem, _ = signer.get_public_key_pem()

        try:
            verified = verify_mandate(mandate.document, kms_pem, now)
        except MandateInvalid as exc:
            rt.event_bus.publish(
                topic="payment-blocked",
                event_type="payment.blocked",
                company_id=rt.settings.COMPANY_ID,
                intent_id=intent.intent_id,
                actor={"type": "service", "id": "payment_gate"},
                data={
                    "reason": "signature_invalid",
                    "detail": f"Mandate verification failed: {exc.detail or exc.code}",
                    "mandate_id": mandate.mandate_id,
                    "blocked_at_step": "verified",
                },
            )
            raise ProblemException(
                409,
                "Mandate signature invalid",
                exc.detail or str(exc),
                type_=f"https://pramaan.example/problems/{exc.code.replace('_', '-')}",
            ) from exc

        # Tamper check: recompute the signed summary from the payment AS IT IS NOW and
        # compare it with what the phone signed, taken from the VERIFIED mandate (never
        # from a database column an attacker with database access could also edit).
        tampered = verified.mandate_fields.get("intent_id") != intent.intent_id
        signed = verified.summary_fields
        if signed.get("kind") == BATCH_KIND:
            # A batch line: this payment must hash to one of the batch's line hashes,
            # and those must hash to the lines_sha256 the phone signed.
            batch = s.get(Batch, signed.get("batch_id", ""))
            stored = (batch.line_hashes or []) if batch is not None else []
            current = line_hash(intent, signed.get("nonce", ""), signed.get("expires_at", ""))
            tampered = (
                tampered
                or not stored
                or lines_digest(stored) != signed.get("lines_sha256")
                or current not in stored
            )
        else:
            current_sha256 = hashlib.sha256(
                canonical_bytes(
                    payment_summary_fields(
                        intent, signed.get("nonce", ""), signed.get("expires_at", "")
                    )
                )
            ).hexdigest()
            tampered = tampered or current_sha256 != verified.summary_sha256.lower()

        if tampered:
            # Tamper detected! Payment must remain held/blocked
            intent.status = "blocked"
            intent.updated_at = now
            rt.event_bus.publish(
                topic="payment-blocked",
                event_type="payment.blocked",
                company_id=rt.settings.COMPANY_ID,
                intent_id=intent.intent_id,
                actor={"type": "service", "id": "payment_gate"},
                data={
                    "reason": "mandate_mismatch",
                    "detail": "The payment differs from what the approver signed. It stays held.",
                    "mandate_id": mandate.mandate_id,
                    "blocked_at_step": "verified",
                },
            )
            try:
                rt.read_model.update_document(
                    "holds",
                    intent.intent_id,
                    {"status": "blocked", "updatedAt": now},
                )
            except Exception:
                pass

            s.commit()

            raise ProblemException(
                409,
                "This payment does not match its approval",
                "The payment differs from what the approver signed. The payment stays held.",
                type_="https://pramaan.example/problems/mandate-mismatch",
            )

        # Release payment
        mandate.used_at = now
        intent.status = "released"
        intent.updated_at = now

        payout_id = new_id("po")
        payout_adapter = SandboxPayout(rt)
        payout_adapter.record_payout(
            payout_id=payout_id,
            mandate_id=mandate.mandate_id,
            intent_id=intent.intent_id,
            amount_paise=str(intent.amount_paise),
            currency=intent.currency,
            payee_name_at_bank=intent.payee_name,
            payee_account_last4=intent.payee_account_last4,
            payee_ifsc=intent.payee_ifsc,
            created_at=now,
        )

        intent_id_val = intent.intent_id
        amount_paise_str = str(intent.amount_paise)

    # Read model update for holds
    try:
        rt.read_model.update_document(
            "holds",
            intent_id_val,
            {"status": "released", "payoutId": payout_id, "updatedAt": now},
        )
    except Exception:
        pass

    # Publish payment.released
    rt.event_bus.publish(
        topic="payment-released",
        event_type="payment.released",
        company_id=rt.settings.COMPANY_ID,
        intent_id=intent_id_val,
        actor={"type": "service", "id": "payment_gate"},
        data={
            "mandate_id": body.mandate_id,
            "payout_id": payout_id,
            "amount_paise": amount_paise_str,
            "rail": "sandbox",
        },
    )

    return {
        "payout_id": payout_id,
        "mandate_id": body.mandate_id,
        "released_at": ist(now),
    }
