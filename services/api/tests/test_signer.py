import pytest

from app.adapters.signer import LocalKeySigner
from app.config import Settings


def test_local_signer_allowed_on_local(local_settings: Settings):
    signer = LocalKeySigner(local_settings)
    pem, key_version = signer.get_public_key_pem()
    assert "BEGIN PUBLIC KEY" in pem
    assert key_version == "mandate-signer/local-1"

    data = b"canonical mandate bytes test"
    sig, ver = signer.sign_mandate(data)
    assert len(sig) > 0
    assert ver == "mandate-signer/local-1"


@pytest.mark.parametrize("env", ["dev", "demo", "prod"])
def test_local_signer_refuses_outside_local(env: str):
    settings = Settings(
        ENV=env,
        GCP_PROJECT="pramaan-dev-515306",
        REGION="asia-south1",
    )
    with pytest.raises(RuntimeError) as exc_info:
        LocalKeySigner(settings)

    assert "LocalKeySigner is only permitted when ENV=local" in str(exc_info.value)
