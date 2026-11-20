"""Tests for device signature verification and dual-signed mandate build & verify."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.adapters.signer import LocalKeySigner
from app.config import Settings
from app.domain.canonical import canonical_bytes
from app.domain.device_signature import SignatureInvalid, verify_device_signature
from app.domain.mandate import MandateInvalid, build_mandate, verify_mandate


@pytest.fixture
def device_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def device_spki_der(device_key) -> bytes:
    return device_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


@pytest.fixture
def local_signer():
    # LocalKeySigner requires ENV=local and ALLOW_TEST_SIGNER=False
    settings = Settings(ENV="local", ALLOW_TEST_SIGNER=False)
    return LocalKeySigner(settings)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 11, 21, 0, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def summary_fields() -> dict[str, str]:
    return {
        "payee_name_at_bank": "Global Trade Solutions",
        "payee_account_last4": "9032",
        "payee_ifsc": "WXYZ0004411",
        "amount_paise": "465000000",
        "currency": "INR",
    }


@pytest.fixture
def device_signature_der(device_key, summary_fields) -> bytes:
    canonical = canonical_bytes(summary_fields)
    return device_key.sign(canonical, ec.ECDSA(hashes.SHA256()))


def test_device_signature_roundtrip_and_flipped_byte(device_key, device_spki_der) -> None:
    """Device signature verifies cleanly; flipped bytes fail with SignatureInvalid."""
    data = b'{"amount_paise":"100000","payee":"Acme"}'
    sig = device_key.sign(data, ec.ECDSA(hashes.SHA256()))

    # 1. Valid signature verifies without error
    verify_device_signature(device_spki_der, data, sig)

    # 2. Flipped byte in signature fails
    corrupted_sig = bytearray(sig)
    corrupted_sig[-5] ^= 0xFF
    with pytest.raises(SignatureInvalid):
        verify_device_signature(device_spki_der, data, bytes(corrupted_sig))

    # 3. Flipped byte in canonical data fails
    corrupted_data = bytearray(data)
    corrupted_data[-1] ^= 0xFF
    with pytest.raises(SignatureInvalid):
        verify_device_signature(device_spki_der, bytes(corrupted_data), sig)

    # 4. Wrong public key fails
    other_key = ec.generate_private_key(ec.SECP256R1())
    other_spki = other_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with pytest.raises(SignatureInvalid):
        verify_device_signature(other_spki, data, sig)


def test_built_mandate_verifies(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """A mandate built with build_mandate passes all 5 verification steps."""
    approval_facts = {
        "intent_id": "pi_01JD2XBOSSSCAM0001",
        "mandate_id": "pm_01JD2XMANDATE0001",
        "decision": "approve",
        "tier": 2,
        "policy_version": "2026.11.1",
        "device_id": "dv_01JD2XCFOPHONE001",
        "approver": "cfo@acme.example",
        "key_security_level": "StrongBox",
        "integrity_verdict": "MEETS_STRONG_INTEGRITY",
        "expires_at": now + timedelta(hours=24),
    }

    doc = build_mandate(
        summary_fields=summary_fields,
        device_spki_der=device_spki_der,
        device_signature_der=device_signature_der,
        approval_facts=approval_facts,
        signer=local_signer,
        now=now,
    )

    kms_pub_pem, _ = local_signer.get_public_key_pem()

    verified = verify_mandate(doc, kms_pub_pem, now)

    assert doc.approval["device_integrity"] == "MEETS_STRONG_INTEGRITY"
    assert verified.decision == "approve"
    assert verified.tier == 2
    assert verified.device_id == "dv_01JD2XCFOPHONE001"
    assert verified.integrity_verdict == "MEETS_STRONG_INTEGRITY"
    assert verified.summary_fields["amount_paise"] == "465000000"
    assert verified.summary_fields["payee_name_at_bank"] == "Global Trade Solutions"
    assert verified.summary_fields["currency"] == "INR"
    assert verified.device_public_key_spki_der == device_spki_der
    assert verified.approver_signature_der == device_signature_der


def test_one_changed_digit_in_amount_inside_summary_b64_fails(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """Tampering with amount in summary_b64 fails at device signature or summary hash check."""
    doc = build_mandate(
        summary_fields=summary_fields,
        device_spki_der=device_spki_der,
        device_signature_der=device_signature_der,
        approval_facts={"tier": 2, "decision": "approve"},
        signer=local_signer,
        now=now,
    )

    # Change 465000000 to 465000001 in summary_b64
    tampered_fields = dict(summary_fields)
    tampered_fields["amount_paise"] = "465000001"
    tampered_summary_b64 = base64.b64encode(canonical_bytes(tampered_fields)).decode("ascii")

    tampered_doc = doc.to_dict()
    tampered_doc["summary_b64"] = tampered_summary_b64

    kms_pub_pem, _ = local_signer.get_public_key_pem()

    with pytest.raises(MandateInvalid) as exc_info:
        verify_mandate(tampered_doc, kms_pub_pem, now)

    assert exc_info.value.code in ("device_signature_invalid", "summary_hash_mismatch")


def test_device_public_key_swapped_fails(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """Swapping device public key causes verification to fail fail-closed."""
    other_key = ec.generate_private_key(ec.SECP256R1())
    other_spki_der = other_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Build mandate with other_spki_der but signature from device_key
    doc = build_mandate(
        summary_fields=summary_fields,
        device_spki_der=other_spki_der,  # Swapped key
        device_signature_der=device_signature_der,
        approval_facts={"tier": 1},
        signer=local_signer,
        now=now,
    )

    kms_pub_pem, _ = local_signer.get_public_key_pem()

    with pytest.raises(MandateInvalid) as exc_info:
        verify_mandate(doc, kms_pub_pem, now)

    assert exc_info.value.code == "device_signature_invalid"


def test_mandate_b64_altered_fails_at_step_a(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """Tampering with mandate_b64 fails at step (a) KMS countersignature verification."""
    doc = build_mandate(
        summary_fields=summary_fields,
        device_spki_der=device_spki_der,
        device_signature_der=device_signature_der,
        approval_facts={"tier": 2},
        signer=local_signer,
        now=now,
    )

    tampered_doc = doc.to_dict()
    # Mutate characters in mandate_b64
    raw_b64 = tampered_doc["mandate_b64"]
    tampered_doc["mandate_b64"] = ("A" if raw_b64[10] != "A" else "B") + raw_b64[1:]

    kms_pub_pem, _ = local_signer.get_public_key_pem()

    with pytest.raises(MandateInvalid) as exc_info:
        verify_mandate(tampered_doc, kms_pub_pem, now)

    assert exc_info.value.code == "kms_signature_invalid"


def test_expired_mandate_fails_at_step_e(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """An expired mandate fails at step (e)."""
    # Create mandate that expired 1 hour ago
    expired_at = now - timedelta(hours=1)
    doc = build_mandate(
        summary_fields=summary_fields,
        device_spki_der=device_spki_der,
        device_signature_der=device_signature_der,
        approval_facts={"expires_at": expired_at},
        signer=local_signer,
        now=now - timedelta(hours=2),
    )

    kms_pub_pem, _ = local_signer.get_public_key_pem()

    with pytest.raises(MandateInvalid) as exc_info:
        verify_mandate(doc, kms_pub_pem, now)

    assert exc_info.value.code == "expired"


def test_mandate_with_device_integrity_in_signed_body_fails(
    summary_fields,
    device_spki_der,
    device_signature_der,
    local_signer,
    now,
) -> None:
    """A mandate whose signed body uses device_integrity instead of integrity_verdict fails."""
    canonical_summary = canonical_bytes(summary_fields)
    summary_b64 = base64.b64encode(canonical_summary).decode("ascii")
    summary_sha256 = hashlib.sha256(canonical_summary).hexdigest().lower()

    # Intentionally use device_integrity instead of integrity_verdict in signed body
    mandate_body = {
        "approver_signature": base64.b64encode(device_signature_der).decode("ascii"),
        "decision": "approve",
        "device_id": "dv_test01",
        "device_public_key": base64.b64encode(device_spki_der).decode("ascii"),
        "expires_at": "2099-12-31T23:59:59Z",
        "device_integrity": "MEETS_STRONG_INTEGRITY",
        "intent_id": "pi_test01",
        "issued_at": "2026-11-20T14:15:00+05:30",
        "key_security_level": "StrongBox",
        "mandate_id": "pm_test01",
        "policy_version": "2026.11.1",
        "signed_at": "2026-11-20T14:15:00+05:30",
        "summary_sha256": summary_sha256,
        "tier": "2",
    }

    canonical_mandate = canonical_bytes(mandate_body)
    mandate_b64 = base64.b64encode(canonical_mandate).decode("ascii")
    kms_sig_der, kms_key_version = local_signer.sign_mandate(canonical_mandate)
    kms_pub_pem, _ = local_signer.get_public_key_pem()

    doc = {
        "mandate_id": "pm_test01",
        "intent_id": "pi_test01",
        "summary_sha256": summary_sha256,
        "summary_b64": summary_b64,
        "mandate_b64": mandate_b64,
        "countersignature": {
            "kms_key_version": kms_key_version,
            "signature": base64.b64encode(kms_sig_der).decode("ascii"),
        },
    }

    with pytest.raises(MandateInvalid) as exc_info:
        verify_mandate(doc, kms_pub_pem, now)

    assert exc_info.value.code in ("invalid_integrity_verdict", "missing_integrity_verdict")


def test_web_verify_fixtures_if_plain_json() -> None:
    """Loads web/verify/src fixtures ONLY IF they are plain JSON files; skips otherwise."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    web_verify_src = repo_root / "web" / "verify" / "src"

    json_fixtures = list(web_verify_src.glob("*.json"))
    if not json_fixtures:
        pytest.skip(
            "No plain JSON fixtures found in web/verify/src (fixtures are inline in TypeScript)"
        )

    for fixture_path in json_fixtures:
        # If any json fixture exists, assert valid JSON
        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, (dict, list))
