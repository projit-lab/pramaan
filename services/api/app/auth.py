import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth

from app.config import Settings, get_settings
from app.domain.models import AuthenticatedUser

_firebase_initialized = False


def _ensure_firebase_app(project_id: str):
    global _firebase_initialized
    if not _firebase_initialized:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={"projectId": project_id})
        _firebase_initialized = True


async def get_current_user(
    x_dev_user: str | None = Header(None, alias="X-Dev-User"),
    authorization: str | None = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    # 1. Check local bypass header
    if x_dev_user:
        if settings.ENV != "local":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"X-Dev-User header is only permitted when ENV=local "
                    f"(current ENV='{settings.ENV}')"
                ),
            )
        return AuthenticatedUser(
            uid=x_dev_user,
            email=f"{x_dev_user}@acme.example",
            roles=["finance", "clerk"],
        )

    # 2. Check Authorization Bearer token
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header or X-Dev-User bypass header.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be in the format 'Bearer <token>'.",
        )

    # 3. Verify Firebase ID token
    _ensure_firebase_app(settings.GCP_PROJECT)
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        uid = decoded_token.get("uid", "")
        email = decoded_token.get("email")
        roles = decoded_token.get("roles", [])
        return AuthenticatedUser(uid=uid, email=email, roles=roles)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase ID token: {str(e)}",
        )
