import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from google.cloud import kms_v1

from app.config import Settings


class LocalKeySigner:
    """Local ECDSA P-256 signer.

    REFUSES to load unless ENV=local.
    Persists key in services/api/.local/dev_key.pem.
    """

    def __init__(self, settings: Settings):
        if settings.ENV != "local":
            raise RuntimeError(
                f"LocalKeySigner is only permitted when ENV=local (current ENV='{settings.ENV}')"
            )

        self.key_dir = Path(__file__).resolve().parent.parent.parent / ".local"
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.key_dir / "dev_key.pem"
        self.key_version = "mandate-signer/local-1"

        self._load_or_generate_key()

    def _load_or_generate_key(self) -> None:
        if self.key_path.exists():
            with open(self.key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(f.read(), password=None)
        else:
            self.private_key = ec.generate_private_key(ec.SECP256R1())
            pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(self.key_path, "wb") as f:
                f.write(pem)

    def sign_mandate(self, canonical_mandate_bytes: bytes) -> tuple[bytes, str]:
        # ec.ECDSA(hashes.SHA256()) returns ASN.1 DER-encoded signature
        signature = self.private_key.sign(
            canonical_mandate_bytes,
            ec.ECDSA(hashes.SHA256()),
        )
        return signature, self.key_version

    def sign(self, canonical_mandate_bytes: bytes) -> tuple[bytes, str]:
        """Alias for sign_mandate."""
        return self.sign_mandate(canonical_mandate_bytes)

    def get_public_key_pem(self) -> tuple[str, str]:
        public_key = self.private_key.public_key()
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return pem, self.key_version


class KmsMandateSigner:
    """Google Cloud KMS Asymmetric Signer.

    Signs with Cloud KMS HSM key 'mandate-signer' (algorithm EC_SIGN_P256_SHA256).
    """

    def __init__(self, settings: Settings):
        self.kms_key_name = settings.KMS_KEY
        self.client = kms_v1.KeyManagementServiceClient()
        self.key_version_name = self._resolve_key_version()

    def _resolve_key_version(self) -> str:
        # If full cryptoKeyVersion is already passed in KMS_KEY, use it
        if "/cryptoKeyVersions/" in self.kms_key_name:
            return self.kms_key_name
        # Otherwise, fetch the enabled version or default to /cryptoKeyVersions/1
        try:
            versions = self.client.list_crypto_key_versions(
                request={"parent": self.kms_key_name, "filter": "state=ENABLED"}
            )
            for v in versions:
                return v.name
        except Exception:
            pass
        return f"{self.kms_key_name}/cryptoKeyVersions/1"

    def sign_mandate(self, canonical_mandate_bytes: bytes) -> tuple[bytes, str]:
        digest = hashlib.sha256(canonical_mandate_bytes).digest()
        request = kms_v1.AsymmetricSignRequest(
            name=self.key_version_name,
            digest=kms_v1.Digest(sha256=digest),
        )
        response = self.client.asymmetric_sign(request=request)
        return response.signature, self.key_version_name

    def sign(self, canonical_mandate_bytes: bytes) -> tuple[bytes, str]:
        """Alias for sign_mandate."""
        return self.sign_mandate(canonical_mandate_bytes)

    def get_public_key_pem(self) -> tuple[str, str]:
        request = kms_v1.GetPublicKeyRequest(name=self.key_version_name)
        public_key = self.client.get_public_key(request=request)
        return public_key.pem, self.key_version_name


def get_mandate_signer(settings: Settings):
    if settings.ENV == "local" and not settings.ALLOW_TEST_SIGNER:
        return LocalKeySigner(settings)
    return KmsMandateSigner(settings)
