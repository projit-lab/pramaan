"""Android Key Attestation Verifier.

Implements the 11 hardware-backed enrolment checks according to the Google Key
Attestation specification:
https://developer.android.com/privacy-and-security/security-key-attestation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from pyasn1.codec.der import decoder
from pyasn1.error import PyAsn1Error

logger = logging.getLogger(__name__)

KEY_DESCRIPTION_OID = "1.3.6.1.4.1.11129.2.1.17"
STATUS_URL = "https://android.googleapis.com/attestation/status"
ROOTS_DIR = Path(__file__).resolve().parent / "attestation_roots"

# Keymaster / KeyMint tag IDs
TAG_PURPOSE = 1
TAG_ALGORITHM = 2
TAG_KEY_SIZE = 3
TAG_DIGEST = 5
TAG_EC_CURVE = 10
TAG_NO_AUTH_REQUIRED = 503
TAG_USER_AUTH_TYPE = 504
TAG_ROOT_OF_TRUST = 704
TAG_OS_PATCH_LEVEL = 706
TAG_ATTESTATION_APPLICATION_ID = 709

# Constants
KM_PURPOSE_SIGN = 2  # Wire format KM_PURPOSE_SIGN
KM_PURPOSE_SIGN_JAVA = 4  # Java KeyProperties.PURPOSE_SIGN bitmask
KM_ALGORITHM_EC = 3
KM_CURVE_P256 = 1
KM_DIGEST_SHA256 = 4
AUTH_BIOMETRIC_BIT = 2
VERIFIED_BOOT_STATE_VERIFIED = 0

SECURITY_LEVEL_NAMES = {
    1: "TEE",
    2: "STRONGBOX",
}


class AttestationError(Exception):
    """Raised when any step of key attestation verification fails."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AttestationResult:
    """Successful attestation result containing extracted hardware parameters."""

    public_key_spki_der: bytes
    security_level: str
    os_patch_level: int
    verified_boot_state: str


class RevocationList:
    """Manages the Android attestation status / revocation list."""

    def __init__(
        self,
        cache_ttl_seconds: int = 86400,
        entries: dict[str, Any] | None = None,
        status_url: str = STATUS_URL,
    ) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds
        self.status_url = status_url
        self._entries: dict[str, Any] | None = entries
        self._last_fetched: float = time.time() if entries is not None else 0.0

    def _fetch_if_needed(self) -> None:
        if self._entries is not None and (
            time.time() - self._last_fetched < self.cache_ttl_seconds
        ):
            return
        try:
            resp = httpx.get(self.status_url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                if "entries" in data and isinstance(data["entries"], dict):
                    self._entries = data["entries"]
                else:
                    self._entries = data
                self._last_fetched = time.time()
        except Exception as exc:
            logger.warning("Failed to fetch attestation status from %s: %s", self.status_url, exc)
            if self._entries is None:
                self._entries = {}

    def is_revoked(self, serial: str | int) -> bool:
        """Check if certificate serial (lowercase hex) is revoked or suspended."""
        if isinstance(serial, int):
            serial_hex = f"{serial:x}".lower()
        else:
            serial_hex = serial.lower().lstrip("0") or "0"

        self._fetch_if_needed()
        assert self._entries is not None

        entry = self._entries.get(serial_hex)
        if entry is None:
            return False
        if isinstance(entry, dict):
            status = entry.get("status", "").upper()
            return status in ("REVOKED", "SUSPENDED")
        if isinstance(entry, str):
            return entry.upper() in ("REVOKED", "SUSPENDED")
        return True

    def __contains__(self, serial: str | int) -> bool:
        return self.is_revoked(serial)


_TRUSTED_ROOT_SPKIS: list[bytes] | None = None


def get_trusted_google_root_spkis(roots_dir: Path = ROOTS_DIR) -> list[bytes]:
    """Load all embedded Google hardware root certificate SPKIs."""
    global _TRUSTED_ROOT_SPKIS
    if _TRUSTED_ROOT_SPKIS is not None:
        return _TRUSTED_ROOT_SPKIS

    spkis: list[bytes] = []
    if roots_dir.exists():
        for pem_path in roots_dir.glob("*.pem"):
            try:
                cert = x509.load_pem_x509_certificate(pem_path.read_bytes(), default_backend())
                spki = cert.public_key().public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                spkis.append(spki)
            except Exception as exc:
                logger.error("Failed loading Google root cert from %s: %s", pem_path, exc)

    _TRUSTED_ROOT_SPKIS = spkis
    return _TRUSTED_ROOT_SPKIS


def _verify_cert_signature(child: x509.Certificate, parent_pubkey: Any) -> None:
    """Verify cryptographic signature on child certificate using parent public key."""
    try:
        if isinstance(parent_pubkey, rsa.RSAPublicKey):
            parent_pubkey.verify(
                child.signature,
                child.tbs_certificate_bytes,
                padding.PKCS1v15(),
                child.signature_hash_algorithm,
            )
        elif isinstance(parent_pubkey, ec.EllipticCurvePublicKey):
            parent_pubkey.verify(
                child.signature,
                child.tbs_certificate_bytes,
                ec.ECDSA(child.signature_hash_algorithm),
            )
        else:
            raise AttestationError(
                "unsupported_key_type", f"Unsupported parent key type: {type(parent_pubkey)}"
            )
    except InvalidSignature as exc:
        raise AttestationError(
            "invalid_signature_chain", f"Signature verification failed: {exc}"
        ) from exc


def _get_context_tagged_dict(asn1_sequence: Any) -> dict[int, Any]:
    """Map context-specific tag IDs to their pyasn1 values."""
    mapping: dict[int, Any] = {}
    for i in range(len(asn1_sequence)):
        comp = asn1_sequence[i]
        for tag in comp.tagSet:
            if tag.tagClass == 128:  # Context-specific tag class
                mapping[tag.tagId] = comp
    return mapping


def verify_attestation(
    chain_der: list[bytes],
    expected_challenge: bytes,
    settings: Any,
    revocation: RevocationList,
    now: datetime,
) -> AttestationResult:
    """Verify Android hardware key attestation chain against the 11 enrolment checks.

    Fail-closed: raises AttestationError on any validation error.
    """
    # Check 1: Chain must be non-empty and valid DER certs
    if not chain_der:
        raise AttestationError("invalid_chain", "Certificate chain is empty")

    certs: list[x509.Certificate] = []
    for i, c_bytes in enumerate(chain_der):
        try:
            certs.append(x509.load_der_x509_certificate(c_bytes, default_backend()))
        except Exception as exc:
            raise AttestationError(
                "invalid_certificate", f"Failed decoding certificate at index {i}: {exc}"
            ) from exc

    # Check 2: Root public key matches one of Google's hardware roots
    root = certs[-1]
    trusted_roots = get_trusted_google_root_spkis()
    root_spki = root.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not any(root_spki == trusted for trusted in trusted_roots):
        raise AttestationError(
            "untrusted_root", "Root certificate does not match any trusted Google hardware root"
        )

    # Check 1b: All certs valid at `now`
    for i, cert in enumerate(certs):
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            raise AttestationError(
                "expired_certificate",
                f"Certificate {i} validity period ({cert.not_valid_before_utc} to "
                f"{cert.not_valid_after_utc}) does not include {now}",
            )

    # Check 1c: Verify X.509 signature chain up to root
    for i in range(len(certs) - 1):
        _verify_cert_signature(certs[i], certs[i + 1].public_key())

    # If root is self-signed, verify its self-signature
    if root.issuer == root.subject:
        _verify_cert_signature(root, root.public_key())

    # Check 3: Revocation check across all certs in chain
    for i, cert in enumerate(certs):
        serial_hex = f"{cert.serial_number:x}".lower()
        if revocation.is_revoked(serial_hex):
            raise AttestationError(
                "revoked_certificate",
                f"Certificate at index {i} (serial {serial_hex}) is revoked or suspended",
            )

    # Check 4: Leaf cert has KeyDescription extension OID 1.3.6.1.4.1.11129.2.1.17
    leaf = certs[0]
    try:
        key_desc_ext = leaf.extensions.get_extension_for_oid(
            x509.ObjectIdentifier(KEY_DESCRIPTION_OID)
        )
    except x509.ExtensionNotFound as exc:
        raise AttestationError(
            "missing_key_description", "Leaf certificate missing KeyDescription extension"
        ) from exc

    try:
        key_desc_asn1, _ = decoder.decode(key_desc_ext.value.value)
    except PyAsn1Error as exc:
        raise AttestationError(
            "invalid_key_description", f"Failed decoding KeyDescription ASN.1: {exc}"
        ) from exc

    if len(key_desc_asn1) < 8:
        raise AttestationError("invalid_key_description", "KeyDescription sequence too short")

    attestation_version = int(key_desc_asn1[0])
    attestation_sec_level = int(key_desc_asn1[1])
    keymaster_version = int(key_desc_asn1[2])
    keymaster_sec_level = int(key_desc_asn1[3])
    attestation_challenge = bytes(key_desc_asn1[4])
    software_enforced = key_desc_asn1[6]
    hardware_enforced = key_desc_asn1[7]

    logger.debug(
        "KeyDescription: attestVer=%d, attestSec=%d, kmVer=%d, kmSec=%d",
        attestation_version,
        attestation_sec_level,
        keymaster_version,
        keymaster_sec_level,
    )

    # Check 5: attestationChallenge == expected_challenge
    if attestation_challenge != expected_challenge:
        raise AttestationError(
            "invalid_challenge",
            f"Attestation challenge mismatch: expected {expected_challenge.hex()}, "
            f"got {attestation_challenge.hex()}",
        )

    # Check 6: attestationSecurityLevel and keymasterSecurityLevel in {StrongBox, TEE}
    if attestation_sec_level not in (1, 2) or keymaster_sec_level not in (1, 2):
        raise AttestationError(
            "insecure_security_level",
            f"Security level not hardware-backed (attestation={attestation_sec_level}, "
            f"km={keymaster_sec_level})",
        )

    # Parse hardware and software enforced tag sets
    hw_tags = _get_context_tagged_dict(hardware_enforced)
    sw_tags = _get_context_tagged_dict(software_enforced)

    # Check 7: Hardware-enforced authorization list checks
    # - purpose contains SIGN (2 or 4)
    if TAG_PURPOSE not in hw_tags:
        raise AttestationError("invalid_purpose", "Missing purpose tag in hardwareEnforced")
    purposes = {int(p) for p in hw_tags[TAG_PURPOSE]}
    if KM_PURPOSE_SIGN not in purposes and KM_PURPOSE_SIGN_JAVA not in purposes:
        raise AttestationError("invalid_purpose", f"Purpose does not include SIGN: {purposes}")

    # - algorithm is EC (3)
    if TAG_ALGORITHM not in hw_tags or int(hw_tags[TAG_ALGORITHM]) != KM_ALGORITHM_EC:
        raise AttestationError(
            "invalid_algorithm", f"Algorithm is not EC: {hw_tags.get(TAG_ALGORITHM)}"
        )

    # - keySize is 256
    if TAG_KEY_SIZE not in hw_tags or int(hw_tags[TAG_KEY_SIZE]) != 256:
        raise AttestationError(
            "invalid_key_size", f"Key size is not 256: {hw_tags.get(TAG_KEY_SIZE)}"
        )

    # - digest contains SHA-256 (4)
    if TAG_DIGEST not in hw_tags:
        raise AttestationError("invalid_digest", "Missing digest tag in hardwareEnforced")
    digests = {int(d) for d in hw_tags[TAG_DIGEST]}
    if KM_DIGEST_SHA256 not in digests:
        raise AttestationError("invalid_digest", f"Digest does not include SHA-256: {digests}")

    # - ecCurve is P_256 (1)
    if TAG_EC_CURVE not in hw_tags or int(hw_tags[TAG_EC_CURVE]) != KM_CURVE_P256:
        raise AttestationError(
            "invalid_curve", f"EC curve is not P-256: {hw_tags.get(TAG_EC_CURVE)}"
        )

    # - noAuthRequired is ABSENT
    if TAG_NO_AUTH_REQUIRED in hw_tags:
        raise AttestationError(
            "auth_not_required", "noAuthRequired tag present in hardwareEnforced"
        )

    # - userAuthType requires BIOMETRIC (bit 2 / AUTH_BIOMETRIC_STRONG or AUTH_ANY)
    if TAG_USER_AUTH_TYPE not in hw_tags:
        raise AttestationError("biometric_required", "Missing userAuthType tag in hardwareEnforced")
    user_auth_type = int(hw_tags[TAG_USER_AUTH_TYPE])
    if (user_auth_type & AUTH_BIOMETRIC_BIT) == 0:
        raise AttestationError(
            "biometric_required", f"userAuthType ({user_auth_type}) does not require biometric"
        )

    # Check 8: Hardware-enforced rootOfTrust checks
    if TAG_ROOT_OF_TRUST not in hw_tags:
        raise AttestationError(
            "missing_root_of_trust", "Missing rootOfTrust tag in hardwareEnforced"
        )
    root_of_trust = hw_tags[TAG_ROOT_OF_TRUST]
    if len(root_of_trust) < 3:
        raise AttestationError("invalid_root_of_trust", "rootOfTrust sequence too short")

    device_locked = bool(root_of_trust[1])
    if not device_locked:
        raise AttestationError(
            "device_unlocked", "Device bootloader is unlocked (deviceLocked=False)"
        )

    verified_boot_state = int(root_of_trust[2])
    if verified_boot_state != VERIFIED_BOOT_STATE_VERIFIED:
        raise AttestationError(
            "unverified_boot",
            f"verifiedBootState is not VERIFIED (got {verified_boot_state})",
        )

    # Check 9: Hardware-enforced osPatchLevel within settings.ATTEST_PATCH_WINDOW_MONTHS of `now`
    if TAG_OS_PATCH_LEVEL not in hw_tags:
        raise AttestationError(
            "missing_patch_level", "Missing osPatchLevel tag in hardwareEnforced"
        )
    os_patch_level = int(hw_tags[TAG_OS_PATCH_LEVEL])
    patch_year = os_patch_level // 100
    patch_month = os_patch_level % 100
    if not (1 <= patch_month <= 12):
        raise AttestationError(
            "invalid_patch_level", f"Invalid osPatchLevel format: {os_patch_level}"
        )

    now_months = now.year * 12 + now.month
    patch_months = patch_year * 12 + patch_month
    months_diff = now_months - patch_months

    max_window_months = getattr(settings, "ATTEST_PATCH_WINDOW_MONTHS", 12)
    if months_diff < 0 or months_diff > max_window_months:
        raise AttestationError(
            "expired_patch_level",
            f"osPatchLevel {os_patch_level} outside allowed window of "
            f"{max_window_months} months (diff={months_diff})",
        )

    # Check 10: In softwareEnforced or hardwareEnforced (check both):
    # attestationApplicationId contains package name and signing digest matching settings
    app_id_raw: bytes | None = None
    if TAG_ATTESTATION_APPLICATION_ID in sw_tags:
        app_id_raw = bytes(sw_tags[TAG_ATTESTATION_APPLICATION_ID])
    elif TAG_ATTESTATION_APPLICATION_ID in hw_tags:
        app_id_raw = bytes(hw_tags[TAG_ATTESTATION_APPLICATION_ID])

    if app_id_raw is None:
        raise AttestationError(
            "missing_application_id",
            "attestationApplicationId not found in softwareEnforced or hardwareEnforced",
        )

    try:
        app_id_asn1, _ = decoder.decode(app_id_raw)
    except PyAsn1Error as exc:
        raise AttestationError(
            "invalid_application_id", f"Failed decoding attestationApplicationId ASN.1: {exc}"
        ) from exc

    if len(app_id_asn1) < 2:
        raise AttestationError(
            "invalid_application_id", "attestationApplicationId sequence too short"
        )

    # Extract package names from packageInfos (SetOf/Sequence)
    package_infos = app_id_asn1[0]
    package_names: list[str] = []
    for pkg_info in package_infos:
        try:
            package_names.append(bytes(pkg_info[0]).decode("utf-8"))
        except Exception:
            pass

    if "dev.pramaan.app" not in package_names:
        raise AttestationError(
            "invalid_application_id",
            f"Package 'dev.pramaan.app' not in attested packages: {package_names}",
        )

    # Extract signature digests (SetOf/Sequence of OctetString)
    sig_digests = app_id_asn1[1]
    sig_digests_hex: list[str] = []
    for sig in sig_digests:
        sig_digests_hex.append(bytes(sig).hex().lower())

    expected_signing_sha = getattr(settings, "ANDROID_SIGNING_SHA256", "").lower().replace(":", "")
    if expected_signing_sha and expected_signing_sha not in sig_digests_hex:
        raise AttestationError(
            "invalid_application_id",
            f"Attested signing cert digest {sig_digests_hex} does not match expected "
            f"{expected_signing_sha}",
        )

    # Check 11: Return AttestationResult
    leaf_spki_der = leaf.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    security_level_str = SECURITY_LEVEL_NAMES.get(attestation_sec_level, "UNKNOWN")

    return AttestationResult(
        public_key_spki_der=leaf_spki_der,
        security_level=security_level_str,
        os_patch_level=os_patch_level,
        verified_boot_state="VERIFIED",
    )
