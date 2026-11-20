import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


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
