"""
FastAPI Application Factory for AutoTrade AI Local Operator API.
Deterministic, localhost-only HTTP interface for Hermes Agent operator tooling.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mobitrade.api.routes import router


def create_app(
    db_path: str = "database/mobitrade.db",
    config_path: str = "configs/default.yaml",
    models_config_path: str = "configs/models.yaml",
) -> FastAPI:
    """
    Factory creating configured FastAPI instance bound to localhost operations.
    """
    app = FastAPI(
        title="AutoTrade AI Local Operator API",
        description="Localhost control and query interface for AutoTrade AI paper trading engine.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Store configurations in application state for dependency resolution
    app.state.db_path = db_path
    app.state.config_path = config_path
    app.state.models_config_path = models_config_path

    # Restrict CORS to localhost only for operator safety
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1",
            "http://127.0.0.1:8000",
            "http://localhost",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(router)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "detail": str(exc),
                "path": request.url.path,
            },
        )

    return app
