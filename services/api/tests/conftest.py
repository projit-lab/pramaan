import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _no_live_revocation_fetch(monkeypatch):
    """Tests never reach Google's attestation status list over the network."""
    from app.domain.attestation import RevocationList
    from app.routers import devices

    monkeypatch.setattr(devices, "get_revocation_list", lambda _s: RevocationList(entries={}))


@pytest.fixture
def local_settings():
    return Settings(
        ENV="local",
        GCP_PROJECT="pramaan-dev-515306",
        REGION="asia-south1",
        KMS_KEY="projects/pramaan-dev-515306/locations/asia-south1/keyRings/pramaan/cryptoKeys/mandate-signer",
    )


@pytest.fixture
def dev_settings():
    return Settings(
        ENV="dev",
        GCP_PROJECT="pramaan-dev-515306",
        REGION="asia-south1",
        KMS_KEY="projects/pramaan-dev-515306/locations/asia-south1/keyRings/pramaan/cryptoKeys/mandate-signer",
    )


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def env(tmp_path):
    """M2 / M2+ API tests: (TestClient, Runtime, Clock) on a fresh seeded database."""
    from tests.test_m2_api import make_env

    return make_env(tmp_path)
