"""
FastAPI Application Entrypoint for Meco Dashboard & Control Centre (Phase 8/9).
Production-hardened with secure logging, CORS validation, and operator authentication.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agents import router as agents_router
from app.api.routes.controls import router as controls_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.health import router as health_router
from app.api.routes.overview import router as overview_router
from app.api.routes.research import router as research_router
from app.api.routes.stream import router as stream_router
from app.api.routes.tokens import router as tokens_router
from app.api.routes.trading import router as trading_router
from app.config.settings import get_settings
from app.security.redaction import setup_secure_logging


def create_app() -> FastAPI:
    """Create and configure the production-hardened Meco API application."""
    setup_secure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Meco Intelligence Dashboard & Control Centre API",
        version="1.0.0",
        description="Comprehensive real-time monitoring and control gateway for Meco intelligence and paper trading operations.",
    )

    # Secure CORS configuration with explicit allowed origins
    origins = [orig.strip() for orig in settings.cors_allowed_origins.split(",") if orig.strip()]
    if not origins:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers under /api prefix
    app.include_router(overview_router, prefix="/api")
    app.include_router(discovery_router, prefix="/api")
    app.include_router(tokens_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    app.include_router(decisions_router, prefix="/api")
    app.include_router(trading_router, prefix="/api")
    app.include_router(research_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(controls_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")

    @app.get("/")
    async def root():
        return {
            "name": "Meco Intelligence API",
            "status": "operational",
            "version": "1.0.0",
            "docs_url": "/docs",
        }

    return app


app = create_app()
