"""Pramaan Dual-Signed Payment Mandate Domain.

Implements build_mandate and verify_mandate according to contracts/mandate.schema.json,
contracts/openapi.yaml, and contracts/README.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.domain.canonical import canonical_bytes
from app.domain.device_signature import SignatureInvalid, verify_device_signature


class MandateInvalid(Exception):
    """Raised when payment mandate verification fails."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MandateDocument:
    """A dual-signed payment mandate document conforming to mandate.schema.json."""

    mandate_id: str
    type: str
    intent_id: str
    summary_sha256: str
    summary_b64: str
    mandate_b64: str
    decision: str
    tier: int
    approval: dict[str, Any]
    countersignature: dict[str, Any]
    expires_at: str
    policy_version: str | None = None
    payer: dict[str, Any] | None = None
    payee: dict[str, Any] | None = None
    amount_paise: str | None = None
    currency: str = "INR"
    purpose: dict[str, Any] | None = None
    initiator: dict[str, Any] | None = None
    signed_at: str | None = None
    used_at: str | None = None

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(item) from exc

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class VerifiedMandate:
    """Verified mandate result containing facts decoded exclusively from the signed bytes."""

    summary_fields: dict[str, str]
    mandate_fields: dict[str, str]
    summary_sha256: str
    decision: str
    tier: int
    device_id: str
    device_public_key_spki_der: bytes
    approver_signature_der: bytes
    signed_at: str
    expires_at: str
    key_security_level: str | None = None
    policy_version: str | None = None
    integrity_verdict: str | None = None
    kms_key_version: str | None = None

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(item) from exc

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


def _format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string preserving timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def build_mandate(
    summary_fields: dict[str, str],
    device_spki_der: bytes,
    device_signature_der: bytes,
    approval_facts: dict[str, Any] | None = None,
    signer: Any = None,
    now: datetime | None = None,
    **kwargs: Any,
) -> MandateDocument:
    """Build a dual-signed MandateDocument according to the schema.

    The approver's phone signs summary_b64 with its hardware key.
    Cloud KMS countersigns mandate_b64 which binds summary_sha256 and the phone's public key.
    """
    facts: dict[str, Any] = {}
    if approval_facts is not None:
        facts.update(approval_facts)
    facts.update(kwargs)

    if signer is None:
        signer = facts.get("signer")
    if signer is None:
        raise ValueError("Signer must be provided to build_mandate")

    if now is None:
        now = facts.get("now")
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Canonicalize summary_fields and compute summary_b64 + summary_sha256
    canonical_summary = canonical_bytes(summary_fields)
    summary_b64 = base64.b64encode(canonical_summary).decode("ascii")
    summary_sha256 = hashlib.sha256(canonical_summary).hexdigest().lower()

    # 2. Extract facts for mandate body
    mandate_id = facts.get("mandate_id") or f"pm_{uuid.uuid4().hex[:16]}"
    intent_id = facts.get("intent_id", f"pi_{uuid.uuid4().hex[:16]}")
    decision = facts.get("decision", "approve")
    tier_val = facts.get("tier", 1)
    tier_int = int(tier_val)
    policy_version = facts.get("policy_version", "2026.11.1")
    device_id = facts.get("device_id", "dv_default")
    approver = facts.get("approver", "approver@example.com")
    key_security_level = facts.get("key_security_level", "StrongBox")
    integrity_verdict = facts.get("integrity_verdict", "")
    patch_level = facts.get("patch_level")

    signed_at_str = _format_timestamp(now)

    expires_at_raw = facts.get("expires_at")
    if isinstance(expires_at_raw, datetime):
        expires_at_str = _format_timestamp(expires_at_raw)
    elif isinstance(expires_at_raw, str):
        expires_at_str = expires_at_raw
    else:
        # Default 24 hour validity
        expires_at_str = _format_timestamp(
            datetime.fromtimestamp(now.timestamp() + 86400, tz=timezone.utc)
        )

    device_pubkey_b64 = base64.b64encode(device_spki_der).decode("ascii")
    device_sig_b64 = base64.b64encode(device_signature_der).decode("ascii")

    # 3. Construct canonical mandate body with string fields per schema
    mandate_body: dict[str, str] = {
        "approver_signature": device_sig_b64,
        "decision": str(decision),
        "device_id": str(device_id),
        "device_public_key": device_pubkey_b64,
        "expires_at": str(expires_at_str),
        "integrity_verdict": str(integrity_verdict),
        "intent_id": str(intent_id),
        "issued_at": str(signed_at_str),
        "key_security_level": str(key_security_level or ""),
        "mandate_id": str(mandate_id),
        "policy_version": str(policy_version or ""),
        "signed_at": str(signed_at_str),
        "summary_sha256": str(summary_sha256),
        "tier": str(tier_int),
    }

    canonical_mandate = canonical_bytes(mandate_body)
    mandate_b64 = base64.b64encode(canonical_mandate).decode("ascii")

    # 4. KMS countersign mandate_bytes
    if hasattr(signer, "sign_mandate"):
        kms_sig_der, kms_key_version = signer.sign_mandate(canonical_mandate)
    elif hasattr(signer, "sign"):
        kms_sig_der, kms_key_version = signer.sign(canonical_mandate)
    else:
        raise TypeError(f"Signer {type(signer)} has neither sign_mandate nor sign method")

    kms_pub_pem: str | None = None
    if hasattr(signer, "get_public_key_pem"):
        try:
            kms_pub_pem, _ = signer.get_public_key_pem()
        except Exception:
            pass

    kms_sig_b64 = base64.b64encode(kms_sig_der).decode("ascii")

    # 5. Assemble outer MandateDocument
    approval = {
        "approver": approver,
        "decision": decision,
        "signed_at": signed_at_str,
        "device_id": device_id,
        "key_security_level": key_security_level,
        "patch_level": patch_level,
        "device_integrity": integrity_verdict if integrity_verdict else None,
        "public_key": device_pubkey_b64,
        "signature": device_sig_b64,
    }

    countersignature = {
        "kms_key_version": kms_key_version,
        "public_key": kms_pub_pem,
        "signature": kms_sig_b64,
        "algorithm": "EC_SIGN_P256_SHA256",
    }

    return MandateDocument(
        mandate_id=mandate_id,
        type="pramaan.payment_mandate.v1",
        intent_id=intent_id,
        summary_sha256=summary_sha256,
        summary_b64=summary_b64,
        mandate_b64=mandate_b64,
        decision=decision,
        tier=tier_int,
        policy_version=policy_version,
        payer=facts.get("payer"),
        payee=facts.get("payee"),
        amount_paise=facts.get("amount_paise"),
        currency=facts.get("currency", "INR"),
        purpose=facts.get("purpose"),
        initiator=facts.get("initiator"),
        approval=approval,
        countersignature=countersignature,
        signed_at=signed_at_str,
        expires_at=expires_at_str,
        used_at=facts.get("used_at"),
    )


def _load_kms_public_key(key: Any) -> ec.EllipticCurvePublicKey:
    """Normalize and load KMS public key as an EllipticCurvePublicKey."""
    if isinstance(key, ec.EllipticCurvePublicKey):
        return key

    if isinstance(key, str):
        key = key.encode("utf-8")

    if isinstance(key, (bytes, bytearray)):
        if b"BEGIN PUBLIC KEY" in key or b"BEGIN CERTIFICATE" in key:
            pub = serialization.load_pem_public_key(key, default_backend())
        else:
            pub = serialization.load_der_public_key(key, default_backend())
        if isinstance(pub, ec.EllipticCurvePublicKey):
            return pub

    raise MandateInvalid("invalid_kms_public_key", f"Unsupported KMS public key: {type(key)}")


def verify_mandate(
    doc: MandateDocument | dict[str, Any],
    kms_public_key: Any,
    now: datetime,
) -> VerifiedMandate:
    """Verify dual-signed mandate in exact fail-closed order.

    Order:
      a) KMS signature over mandate_b64 bytes
      b) Device public key taken ONLY from INSIDE the verified mandate_b64
      c) Device signature over summary_b64 bytes
      d) sha256(summary bytes) == mandate.summary_sha256
      e) Not expired at now

    Returns:
      VerifiedMandate constructed strictly from the signed bytes.

    Raises:
      MandateInvalid on any verification failure.
    """
    # Extract mandate_b64 and summary_b64 from doc
    if isinstance(doc, dict):
        mandate_b64 = doc.get("mandate_b64")
        summary_b64 = doc.get("summary_b64")
        countersignature = doc.get("countersignature") or {}
    else:
        mandate_b64 = doc.mandate_b64
        summary_b64 = doc.summary_b64
        countersignature = doc.countersignature

    if not mandate_b64 or not isinstance(mandate_b64, str):
        raise MandateInvalid("missing_mandate_b64", "Mandate is missing mandate_b64")
    if not summary_b64 or not isinstance(summary_b64, str):
        raise MandateInvalid("missing_summary_b64", "Mandate is missing summary_b64")

    # Step a: KMS signature over the mandate_b64 bytes
    try:
        mandate_bytes = base64.b64decode(mandate_b64)
    except Exception as exc:
        raise MandateInvalid(
            "invalid_mandate_b64", f"Failed decoding base64 mandate: {exc}"
        ) from exc

    kms_pub = _load_kms_public_key(kms_public_key)

    kms_sig_str = countersignature.get("signature")
    if not kms_sig_str or not isinstance(kms_sig_str, str):
        raise MandateInvalid("kms_signature_invalid", "Missing KMS countersignature")

    try:
        kms_sig_der = base64.b64decode(kms_sig_str)
    except Exception as exc:
        raise MandateInvalid(
            "kms_signature_invalid", f"Failed decoding KMS signature base64: {exc}"
        ) from exc

    try:
        kms_pub.verify(kms_sig_der, mandate_bytes, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise MandateInvalid(
            "kms_signature_invalid", f"KMS countersignature verification failed: {exc}"
        ) from exc
    except Exception as exc:
        raise MandateInvalid(
            "kms_signature_invalid", f"Error verifying KMS countersignature: {exc}"
        ) from exc

    # Parse verified mandate body
    try:
        mandate_fields: dict[str, Any] = json.loads(mandate_bytes.decode("utf-8"))
    except Exception as exc:
        raise MandateInvalid(
            "invalid_mandate_body", f"Failed parsing decoded mandate JSON: {exc}"
        ) from exc

    # Enforce integrity_verdict ONLY inside signed mandate (never device_integrity)
    if "device_integrity" in mandate_fields:
        raise MandateInvalid(
            "invalid_integrity_verdict",
            "Mandate body uses device_integrity instead of integrity_verdict",
        )
    if "integrity_verdict" not in mandate_fields:
        raise MandateInvalid(
            "missing_integrity_verdict",
            "Mandate body must contain integrity_verdict",
        )

    # Step b: Take device_public_key from INSIDE the verified mandate
    device_pubkey_b64 = mandate_fields.get("device_public_key")
    if not device_pubkey_b64 or not isinstance(device_pubkey_b64, str):
        raise MandateInvalid(
            "missing_device_public_key", "Device public key not found inside mandate_b64"
        )

    try:
        device_spki_der = base64.b64decode(device_pubkey_b64)
    except Exception as exc:
        raise MandateInvalid(
            "invalid_device_public_key", f"Failed decoding device public key base64: {exc}"
        ) from exc

    # Step c: Device signature over summary_b64 bytes
    try:
        summary_bytes = base64.b64decode(summary_b64)
    except Exception as exc:
        raise MandateInvalid("invalid_summary_b64", f"Failed decoding summary_b64: {exc}") from exc

    approver_sig_b64 = mandate_fields.get("approver_signature")
    if not approver_sig_b64 or not isinstance(approver_sig_b64, str):
        raise MandateInvalid(
            "device_signature_invalid", "Approver signature not found inside mandate_b64"
        )

    try:
        approver_sig_der = base64.b64decode(approver_sig_b64)
    except Exception as exc:
        raise MandateInvalid(
            "device_signature_invalid", f"Failed decoding approver signature base64: {exc}"
        ) from exc

    try:
        verify_device_signature(device_spki_der, summary_bytes, approver_sig_der)
    except SignatureInvalid as exc:
        raise MandateInvalid(
            "device_signature_invalid", f"Device signature check failed: {exc}"
        ) from exc

    # Step d: sha256(summary bytes) == mandate.summary_sha256
    calc_sha256 = hashlib.sha256(summary_bytes).hexdigest().lower()
    expected_sha256 = str(mandate_fields.get("summary_sha256", "")).lower()

    if calc_sha256 != expected_sha256:
        raise MandateInvalid(
            "summary_hash_mismatch",
            f"Summary hash mismatch: calculated {calc_sha256} does not match "
            f"mandate summary_sha256 {expected_sha256}",
        )

    # Step e: Not expired at now
    expires_at_str = mandate_fields.get("expires_at")
    if not expires_at_str or not isinstance(expires_at_str, str):
        raise MandateInvalid("expired", "Missing expires_at inside mandate_b64")

    try:
        expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    except Exception as exc:
        raise MandateInvalid(
            "expired", f"Failed parsing expires_at ({expires_at_str}): {exc}"
        ) from exc

    if expires_at_dt.tzinfo is None:
        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)

    now_cmp = now
    if now_cmp.tzinfo is None:
        now_cmp = now_cmp.replace(tzinfo=timezone.utc)

    if now_cmp > expires_at_dt:
        raise MandateInvalid(
            "expired", f"Mandate expired at {expires_at_str} (verification time: {now})"
        )

    # Decode summary fields strictly from summary_bytes
    try:
        summary_fields_decoded: dict[str, Any] = json.loads(summary_bytes.decode("utf-8"))
        summary_fields: dict[str, str] = {str(k): str(v) for k, v in summary_fields_decoded.items()}
    except Exception as exc:
        raise MandateInvalid(
            "invalid_summary_body", f"Failed parsing decoded summary JSON: {exc}"
        ) from exc

    tier_int = int(mandate_fields.get("tier", 0))

    return VerifiedMandate(
        summary_fields=summary_fields,
        mandate_fields={str(k): str(v) for k, v in mandate_fields.items()},
        summary_sha256=expected_sha256,
        decision=str(mandate_fields.get("decision", "")),
        tier=tier_int,
        device_id=str(mandate_fields.get("device_id", "")),
        device_public_key_spki_der=device_spki_der,
        approver_signature_der=approver_sig_der,
        signed_at=str(mandate_fields.get("signed_at", "")),
        expires_at=expires_at_str,
        key_security_level=mandate_fields.get("key_security_level"),
        policy_version=mandate_fields.get("policy_version"),
        integrity_verdict=mandate_fields.get("integrity_verdict"),
        kms_key_version=countersignature.get("kms_key_version"),
    )
