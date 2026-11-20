from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import (
    ProblemException,
    generic_exception_handler,
    http_exception_handler,
    problem_exception_handler,
    validation_exception_handler,
)
from app.adapters.voice_demo import wire_voice_demo
from app.logging import setup_logging
from app.routers import (
    approvals,
    health,
    hierarchy,
    intents,
    keys,
    local_dev,
    mandates,
    master,
    voice,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger = setup_logging()
    logger.info(
        f"Starting Pramaan API Service (env={settings.ENV}, "
        f"version={settings.VERSION}, project={settings.GCP_PROJECT})"
    )
    yield
    logger.info("Stopping Pramaan API Service")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Pramaan API",
        version=settings.VERSION,
        description="Pramaan payment gate and mandate verification API.",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register RFC 9457 Problem Details Exception Handlers
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(ProblemException, problem_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Routers mounted at /v1 and for convenience at root
    app.include_router(health.router, prefix="/v1")
    app.include_router(health.router)  # /health and /healthz
    app.include_router(keys.router, prefix="/v1")
    app.include_router(keys.router)  # /keys/countersign

    # M2 (Danish): intents, approvals list, mandates, vendor master, policies.
    # M2+ (Danish): organisation tree, approver hierarchy, batches, standing mandates.
    for module in (intents, approvals, mandates, master, hierarchy):
        app.include_router(module.router, prefix="/v1")

    # M4 (Danish, ported into this layout by Shoaib): the Tier 2 spoken check.
    # The endpoint exists and is contract-shaped, but its three dependencies are
    # still in-memory stand-ins, so it is wired only when ENV=local. Putting it
    # into the real approval flow -- after the Tier 1 signature has verified,
    # able only to add a check -- is Phase 6.
    app.include_router(voice.router, prefix="/v1")

    if settings.ENV == "local":
        app.include_router(local_dev.router, prefix="/v1")
        wire_voice_demo(app)

    return app


app = create_app()
