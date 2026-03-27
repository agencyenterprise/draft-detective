"""
FastAPI application entry point

This module sets up the FastAPI application, middleware, and registers routers.
Business logic is organized in separate routers under api/routers/.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from api.routers import (
    analysis,
    app_configs,
    feedback,
    files,
    health,
    issues,
    logs,
    projects,
    public,
    share,
    users,
    workflows,
    workflow_types,
)
from api.routers.tus_upload import tus_router
from lib.config.logger import setup_logger

setup_logger()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Seed default runtime configs on startup."""
    from lib.services.app_configs import seed_all_defaults

    await seed_all_defaults()
    yield


app = FastAPI(title="AI Analyst API", lifespan=lifespan)


class TusTerminationMiddleware(BaseHTTPMiddleware):
    """Handle TUS termination 404s gracefully - treat as already deleted."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # TUS DELETE on completed uploads returns 404 - treat as success
        if (
            request.method == "DELETE"
            and request.url.path.startswith("/tus/")
            and response.status_code == 404
        ):
            return Response(status_code=204)
        return response


app.add_middleware(TusTerminationMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to only our own origin later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose Tus headers so frontend can read them
    expose_headers=[
        "Upload-Offset",
        "Upload-Length",
        "Upload-Expires",
        "Tus-Version",
        "Tus-Resumable",
        "Tus-Extension",
        "Tus-Max-Size",
        "Location",
    ],
)

# Gzip middleware
app.add_middleware(GZipMiddleware)

# Register routers
app.include_router(health.router)
app.include_router(app_configs.router)
app.include_router(analysis.router)
app.include_router(workflows.router)
app.include_router(workflow_types.router)
app.include_router(files.router)
app.include_router(feedback.router)
app.include_router(logs.router)
app.include_router(issues.router)
app.include_router(projects.router)
app.include_router(share.router)
app.include_router(public.router)
app.include_router(tus_router)
app.include_router(users.router)
