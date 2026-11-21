from http import HTTPStatus
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemException(Exception):
    def __init__(
        self,
        status_code: int,
        title: str | None = None,
        detail: str | None = None,
        type_: str | None = None,
        errors: list[dict[str, str]] | None = None,
    ):
        self.status_code = status_code
        self.title = title or HTTPStatus(status_code).phrase
        self.detail = detail
        self.type = type_ or f"urn:problem:{status_code}"
        self.errors = errors
        super().__init__(detail or self.title)


def create_problem_response(
    status_code: int,
    title: str,
    detail: str | None,
    instance: str,
    type_: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": type_ or f"urn:problem:{status_code}",
        "title": title,
        "status": status_code,
        "instance": instance,
    }
    if detail:
        content["detail"] = detail
    if errors:
        content["errors"] = errors

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    title = HTTPStatus(exc.status_code).phrase
    return create_problem_response(
        status_code=exc.status_code,
        title=title,
        detail=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        instance=request.url.path,
    )


async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
    return create_problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        instance=request.url.path,
        type_=exc.type,
        errors=exc.errors,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        field_loc = ".".join(str(loc) for loc in err.get("loc", []))
        errors.append(
            {
                "field": field_loc,
                "detail": err.get("msg", "Invalid value"),
            }
        )

    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="Invalid request body or parameters.",
        instance=request.url.path,
        type_="urn:problem:validation-error",
        errors=errors,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred processing your request.",
        instance=request.url.path,
        type_="urn:problem:internal-server-error",
    )
