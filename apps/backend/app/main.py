"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded  # type: ignore[import-untyped]

from app.accounts.router import router as accounts_router
from app.admin.middleware import ReadOnlyMiddleware
from app.admin.router import router as admin_router
from app.audit.router import router as audit_router
from app.budgets.router import router as budgets_router
from app.classification.router import router as classification_router
from app.config import get_settings
from app.debts.router import router as debts_router
from app.goals.router import router as goals_router
from app.households.router import router as households_router
from app.ingest.router import router as ingest_router
from app.insights.router import router as insights_router
from app.platform.router import router as platform_router
from app.projections.router import router as projections_router
from app.recommendations.router import router as recommendations_router
from app.recurrences.router import router as recurrences_router
from app.security.ratelimit import get_limiter, rate_limit_exceeded_handler
from app.settings.router import router as settings_router
from app.transactions.router import router as transactions_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Register cross-module lifecycle callbacks at startup."""
    from app.classification.service import seed_default_categories
    from app.database import get_session_factory
    from app.households.bootstrap import run_bootstrap
    from app.platform.events import register_on_household_created

    register_on_household_created(seed_default_categories)

    factory = get_session_factory()
    async with factory() as session:
        await run_bootstrap(session)

    _app.state.started_at = datetime.now(tz=UTC)
    from app.platform.app_state import set_started_at

    set_started_at(_app.state.started_at)
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

    # Read-only enforcement — checked before all other middleware
    app.add_middleware(ReadOnlyMiddleware)

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
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(accounts_router, prefix="/api/v1")
    app.include_router(transactions_router, prefix="/api/v1")
    app.include_router(classification_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(recurrences_router, prefix="/api/v1")
    app.include_router(recommendations_router, prefix="/api/v1")
    app.include_router(budgets_router, prefix="/api/v1")
    app.include_router(debts_router, prefix="/api/v1")
    app.include_router(goals_router, prefix="/api/v1")
    app.include_router(projections_router, prefix="/api/v1")
    app.include_router(insights_router, prefix="/api/v1")
    app.include_router(platform_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")

    return app


app = create_app()
