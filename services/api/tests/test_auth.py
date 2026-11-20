import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.domain.models import AuthenticatedUser
from app.errors import http_exception_handler


def make_test_app(settings: Settings):
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    @app.get("/test/protected")
    async def protected_endpoint(user: AuthenticatedUser = Depends(get_current_user)):
        return {"uid": user.uid, "email": user.email, "roles": user.roles}

    return app


@pytest.mark.anyio
async def test_auth_bypass_allowed_on_local(local_settings: Settings):
    app = make_test_app(local_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/test/protected", headers={"X-Dev-User": "clerk_alice"})

    assert res.status_code == 200
    data = res.json()
    assert data["uid"] == "clerk_alice"
    assert "clerk" in data["roles"]


@pytest.mark.anyio
@pytest.mark.parametrize("env", ["dev", "demo", "prod"])
async def test_auth_bypass_refused_outside_local(env: str):
    settings = Settings(
        ENV=env,
        GCP_PROJECT="pramaan-dev-515306",
        REGION="asia-south1",
    )
    app = make_test_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/test/protected", headers={"X-Dev-User": "clerk_alice"})

    assert res.status_code == 403
    assert res.headers["content-type"] == "application/problem+json"
    problem = res.json()
    assert problem["status"] == 403
    assert "X-Dev-User header is only permitted when ENV=local" in problem["detail"]
    assert problem["type"] == "urn:problem:403"


@pytest.mark.anyio
async def test_auth_missing_credentials(local_settings: Settings):
    app = make_test_app(local_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/test/protected")

    assert res.status_code == 401
    assert res.headers["content-type"] == "application/problem+json"
    problem = res.json()
    assert problem["status"] == 401
    assert "Missing Authorization header" in problem["detail"]
