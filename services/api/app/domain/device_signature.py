"""Device Signature Verification.

Verifies approver phone hardware-bound signatures using ECDSA P-256 SHA-256.
"""

from __future__ import annotations

from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class SignatureInvalid(Exception):
    """Raised when an approver device signature verification fails."""

    pass


def verify_device_signature(spki_der: bytes, canonical: bytes, signature_der: bytes) -> None:
    """Verify an approver device's ECDSA P-256 SHA-256 signature.

    Args:
        spki_der: SubjectPublicKeyInfo DER encoded public key bytes.
        canonical: The exact canonical bytes that were signed.
        signature_der: The ASN.1 DER encoded signature bytes.

    Raises:
        SignatureInvalid: If public key is invalid, not P-256, or signature fails verification.
    """
    if not spki_der:
        raise SignatureInvalid("Device public key SPKI DER is empty")
    if not canonical:
        raise SignatureInvalid("Canonical bytes to verify are empty")
    if not signature_der:
        raise SignatureInvalid("Device signature DER is empty")

    try:
        public_key: Any = serialization.load_der_public_key(spki_der, default_backend())
    except Exception as exc:
        raise SignatureInvalid(f"Failed decoding device public key SPKI DER: {exc}") from exc

    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise SignatureInvalid(
            f"Public key is not an EllipticCurvePublicKey (got {type(public_key).__name__})"
        )

    if not isinstance(public_key.curve, ec.SECP256R1):
        raise SignatureInvalid(
            f"Public key curve is not P-256 (SECP256R1, got {public_key.curve.name})"
        )

    try:
        public_key.verify(
            signature_der,
            canonical,
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise SignatureInvalid(f"Cryptographic signature verification failed: {exc}") from exc
    except Exception as exc:
        raise SignatureInvalid(f"Error during signature verification: {exc}") from exc
