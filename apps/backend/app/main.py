"""FastAPI application factory."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="WDIAG — Where Did It All Go",
        description="Personal finance budgeting and intelligence",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Built-in endpoints
    # ---------------------------------------------------------------------------

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Prometheus metrics are exposed at /metrics by prometheus-client's
    # make_asgi_app(). Mounted once modules are set up.
    # TODO: mount prometheus metrics app after initial module setup

    # ---------------------------------------------------------------------------
    # Module routers — registered here as modules are built out
    # ---------------------------------------------------------------------------
    # from app.households.router import router as households_router
    # app.include_router(households_router, prefix="/api/v1")

    return app


app = create_app()
