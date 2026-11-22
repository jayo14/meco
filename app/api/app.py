"""
FastAPI Application Entrypoint for Meco Dashboard & Control Centre (Phase 8).
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


def create_app() -> FastAPI:
    """Create and configure the Meco API application."""
    app = FastAPI(
        title="Meco Intelligence Dashboard & Control Centre API",
        version="1.0.0",
        description="Comprehensive real-time monitoring and control gateway for Meco intelligence and paper trading operations.",
    )

    # CORS Middleware allowing local frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
