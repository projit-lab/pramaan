"""Role checks for the M2 routes, on top of the skeleton's get_current_user."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.auth import get_current_user
from app.domain.models import AuthenticatedUser
from app.errors import ProblemException


def require_roles(*allowed: str) -> Callable[..., AuthenticatedUser]:
    async def check(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not set(user.roles) & set(allowed):
            raise ProblemException(
                403, "No access", f"This needs one of these roles: {', '.join(allowed)}."
            )
        return user

    return check


async def require_email(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.email:
        raise ProblemException(403, "No access", "This account has no work email.")
    return user
