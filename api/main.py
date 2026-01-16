"""
FastAPI application entry point

This module sets up the FastAPI application, middleware, and registers routers.
Business logic is organized in separate routers under api/routers/.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api.routers import (
    analysis,
    evaluation,
    feedback,
    files,
    health,
    progress,
    projects,
    public,
    share,
    users,
    workflows,
    workflow_types,
)
from lib.config.logger import setup_logger

setup_logger()

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Analyst API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to only our own origin later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip middleware
app.add_middleware(GZipMiddleware)

# Register routers
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(evaluation.router)
app.include_router(workflows.router)
app.include_router(workflow_types.router)
app.include_router(files.router)
app.include_router(feedback.router)
app.include_router(projects.router)
app.include_router(progress.router)
app.include_router(share.router)
app.include_router(public.router)
app.include_router(users.router)
