"""Tests for Android key attestation verification."""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.config import Settings
from app.domain.attestation import (
    AttestationError,
    RevocationList,
    verify_attestation,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def phone_fixture() -> dict:
    fixture_path = FIXTURES_DIR / "attestation_real_phone.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def chain_der(phone_fixture: dict) -> list[bytes]:
    return [base64.b64decode(c) for c in phone_fixture["chain_b64"]]


@pytest.fixture
def expected_challenge(phone_fixture: dict) -> bytes:
    return base64.b64decode(phone_fixture["challenge_b64"])


@pytest.fixture
def capture_now() -> datetime:
    # Fixed point in time matching when the real phone certificate chain was captured
    # (Capture time: 2026-11-20T18:38:49Z / 2026-11-21 00:08:49 IST)
    return datetime(2026, 11, 21, 0, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def default_settings() -> Settings:
    return Settings(
        ATTEST_PATCH_WINDOW_MONTHS=12,
        ANDROID_SIGNING_SHA256="3313d44bb45e66849411470eeffa85a49a66bc9d1a9718a2463b98898d93d968",
    )


@pytest.fixture
def empty_revocation() -> RevocationList:
    return RevocationList(entries={})


def test_real_phone_attestation_passes(
    chain_der: list[bytes],
    expected_challenge: bytes,
    default_settings: Settings,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Real phone attestation chain passes all 11 checks."""
    result = verify_attestation(
        chain_der=chain_der,
        expected_challenge=expected_challenge,
        settings=default_settings,
        revocation=empty_revocation,
        now=capture_now,
    )

    assert result.security_level == "STRONGBOX"
    assert result.os_patch_level == 202610
    assert result.verified_boot_state == "VERIFIED"
    assert len(result.public_key_spki_der) == 91


def test_negative_wrong_challenge(
    chain_der: list[bytes],
    default_settings: Settings,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when challenge does not match."""
    wrong_challenge = b"\x00" * 32
    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=chain_der,
            expected_challenge=wrong_challenge,
            settings=default_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "invalid_challenge"


def test_negative_revoked_serial(
    chain_der: list[bytes],
    expected_challenge: bytes,
    default_settings: Settings,
    capture_now: datetime,
) -> None:
    """Verification fails closed when any cert in the chain is revoked."""
    # Serial of leaf cert is 0x1
    revocation = RevocationList(entries={"1": {"status": "REVOKED", "reason": "KEY_COMPROMISE"}})

    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=chain_der,
            expected_challenge=expected_challenge,
            settings=default_settings,
            revocation=revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "revoked_certificate"


def test_negative_replaced_root(
    chain_der: list[bytes],
    expected_challenge: bytes,
    default_settings: Settings,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when the root is not a trusted Google hardware root."""
    # Generate an untrusted self-signed root certificate
    priv = ec.generate_private_key(ec.SECP384R1(), default_backend())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Untrusted Attestation Root")])
    untrusted_root = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(priv.public_key())
        .serial_number(99999)
        .not_valid_before(capture_now - timedelta(days=10))
        .not_valid_after(capture_now + timedelta(days=10))
        .sign(priv, hashes.SHA384(), default_backend())
    )
    tampered_chain = chain_der[:-1] + [untrusted_root.public_bytes(serialization.Encoding.DER)]

    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=tampered_chain,
            expected_challenge=expected_challenge,
            settings=default_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "untrusted_root"


def test_negative_corrupted_leaf(
    chain_der: list[bytes],
    expected_challenge: bytes,
    default_settings: Settings,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when the leaf certificate signature is corrupted."""
    # Corrupt the signature bytes at the end of the leaf cert
    corrupted_leaf = bytearray(chain_der[0])
    corrupted_leaf[-10] ^= 0xFF
    corrupted_chain = [bytes(corrupted_leaf)] + chain_der[1:]

    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=corrupted_chain,
            expected_challenge=expected_challenge,
            settings=default_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code in ("invalid_signature_chain", "invalid_certificate")


def test_negative_wrong_app_id(
    chain_der: list[bytes],
    expected_challenge: bytes,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when the app signing certificate digest does not match settings."""
    wrong_settings = Settings(
        ATTEST_PATCH_WINDOW_MONTHS=12,
        ANDROID_SIGNING_SHA256="0000000000000000000000000000000000000000000000000000000000000000",
    )
    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=chain_der,
            expected_challenge=expected_challenge,
            settings=wrong_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "invalid_application_id"


def test_negative_expired_patch_level(
    chain_der: list[bytes],
    expected_challenge: bytes,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when OS patch level is older than the configured window."""
    # osPatchLevel is 202610; capture_now is November 2026 (1 month diff)
    # Setting window to 0 months forces patch expiry error
    tight_settings = Settings(
        ATTEST_PATCH_WINDOW_MONTHS=0,
        ANDROID_SIGNING_SHA256="3313d44bb45e66849411470eeffa85a49a66bc9d1a9718a2463b98898d93d968",
    )
    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=chain_der,
            expected_challenge=expected_challenge,
            settings=tight_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "expired_patch_level"


def test_negative_expired_certificate(
    chain_der: list[bytes],
    expected_challenge: bytes,
    default_settings: Settings,
    empty_revocation: RevocationList,
) -> None:
    """Verification fails closed when certificate chain is expired at `now`."""
    # Intermediate cert expires on 2026-11-23; test with 2027-01-01
    future_now = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=chain_der,
            expected_challenge=expected_challenge,
            settings=default_settings,
            revocation=empty_revocation,
            now=future_now,
        )
    assert exc_info.value.code == "expired_certificate"


def test_negative_empty_chain(
    expected_challenge: bytes,
    default_settings: Settings,
    empty_revocation: RevocationList,
    capture_now: datetime,
) -> None:
    """Verification fails closed when certificate chain is empty."""
    with pytest.raises(AttestationError) as exc_info:
        verify_attestation(
            chain_der=[],
            expected_challenge=expected_challenge,
            settings=default_settings,
            revocation=empty_revocation,
            now=capture_now,
        )
    assert exc_info.value.code == "invalid_chain"


def test_revocation_list_functionality() -> None:
    """RevocationList handles serial numbers in int and hex formats."""
    rev_list = RevocationList(
        entries={
            "3323490da2f1ab1fa64ab8356deb577": {"status": "REVOKED"},
            "abcd": {"status": "SUSPENDED"},
            "1": {"status": "REVOKED"},
        }
    )
    assert rev_list.is_revoked("3323490da2f1ab1fa64ab8356deb577")
    assert rev_list.is_revoked(0x3323490DA2F1AB1FA64AB8356DEB577)
    assert "abcd" in rev_list
    assert 1 in rev_list
    assert "01" in rev_list
    assert not rev_list.is_revoked("nonexistent")
