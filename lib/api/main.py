"""
FastAPI application entry point

This module sets up the FastAPI application, middleware, and registers routers.
Business logic is organized in separate routers under api/routers/.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastmcp.utilities.lifespan import combine_lifespans

from lib.api.mcp.server import mcp_app, mcp_auth
from lib.api.mcp_middlewares import MCPTrailingSlashMiddleware
from lib.api.tus_middleware import TusTerminationMiddleware
from lib.api.routers import (
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
    workflow_types,
    workflows,
)
from lib.api.routers.tus_upload import tus_router
from lib.config.logger import setup_logger
from lib.services.workflow_reaper import run_reaper_loop

setup_logger()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed default runtime configs on startup; close shared pools on shutdown."""
    # `seed_all_defaults` and `close_checkpointer_pool` stay lazy to keep the
    # import graph simple — they pull in services that don't need to load on
    # every test that imports main.py.
    from lib.services.app_configs import seed_all_defaults
    from lib.workflows.checkpointer import close_checkpointer_pool

    await seed_all_defaults()
    reaper_task = asyncio.create_task(run_reaper_loop(), name="workflow-reaper")
    try:
        yield
    finally:
        reaper_task.cancel()
        try:
            await reaper_task
        except asyncio.CancelledError:
            pass
        await close_checkpointer_pool()


app = FastAPI(
    title="AI Analyst API",
    lifespan=combine_lifespans(lifespan, mcp_app.lifespan),
)

# OAuth discovery routes must be at the origin root per RFC 8414 / RFC 9728.
# The MCP app is mounted at /mcp, but clients look for .well-known at /.
for route in mcp_auth.get_well_known_routes(mcp_path="/"):
    app.routes.insert(0, route)

app.mount("/mcp", mcp_app)

app.add_middleware(MCPTrailingSlashMiddleware)
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
