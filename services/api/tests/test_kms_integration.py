import os

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.adapters.signer import KmsMandateSigner
from app.config import Settings


@pytest.mark.skipif(
    os.environ.get("RUN_GCP_TESTS") != "1",
    reason="Live GCP KMS integration test: set RUN_GCP_TESTS=1 to execute",
)
def test_kms_asymmetric_sign_and_verify():
    """Live integration test: signs canonical mandate bytes with Cloud KMS HSM key

    and verifies signature with the public key fetched from Cloud KMS.
    """
    settings = Settings(
        ENV="dev",
        GCP_PROJECT="pramaan-dev-515306",
        REGION="asia-south1",
        KMS_KEY="projects/pramaan-dev-515306/locations/asia-south1/keyRings/pramaan/cryptoKeys/mandate-signer",
    )

    signer = KmsMandateSigner(settings)

    # 1. Fetch public key
    pem, key_version = signer.get_public_key_pem()
    assert "BEGIN PUBLIC KEY" in pem
    assert "pramaan/cryptoKeys/mandate-signer/cryptoKeyVersions/" in key_version

    # 2. Canonical mandate bytes to sign
    canonical_mandate_bytes = (
        b'{"decision":"approve","device_id":"dv_test01",'
        b'"summary_sha256":"9f1c2b7a4d6e8f0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f607182",'
        b'"tier":1}'
    )

    # 3. Sign with KMS HSM key
    sig_der, signed_key_version = signer.sign_mandate(canonical_mandate_bytes)
    assert len(sig_der) > 0
    assert signed_key_version == key_version

    # 4. Cryptographically verify signature against public key
    public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
    assert isinstance(public_key, ec.EllipticCurvePublicKey)

    # public_key.verify() raises InvalidSignature if signature does not match
    public_key.verify(
        sig_der,
        canonical_mandate_bytes,
        ec.ECDSA(hashes.SHA256()),
    )
