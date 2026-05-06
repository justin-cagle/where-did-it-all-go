"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded  # type: ignore[import-untyped]

from app.accounts.router import router as accounts_router
from app.classification.router import router as classification_router
from app.config import get_settings
from app.households.router import router as households_router
from app.ingest.router import router as ingest_router
from app.security.ratelimit import get_limiter, rate_limit_exceeded_handler
from app.transactions.router import router as transactions_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Register cross-module lifecycle callbacks at startup."""
    from app.classification.service import seed_default_categories
    from app.platform.events import register_on_household_created

    register_on_household_created(seed_default_categories)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="WDIAG — Where Did It All Go",
        description="Personal finance budgeting and intelligence",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    limiter = get_limiter()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # ---------------------------------------------------------------------------
    # Built-in endpoints
    # ---------------------------------------------------------------------------

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    # ---------------------------------------------------------------------------
    # Module routers
    # ---------------------------------------------------------------------------

    app.include_router(households_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(transactions_router, prefix="/api/v1")
    app.include_router(classification_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")

    return app


app = create_app()
