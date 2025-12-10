"""
FastAPI application entry point

This module sets up the FastAPI application, middleware, and registers routers.
Business logic is organized in separate routers under api/routers/.
"""

import logging
from datetime import datetime

from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, create_model

from api.auth import get_current_user
from api.models import StartWorkflowResponse
from api.routers import (
    analysis,
    evaluation,
    feedback,
    files,
    health,
    projects,
    workflows,
)
from api.services.workflow_runner import start_workflow_run
from lib.config.logger import setup_logger
from lib.models.user import User
from lib.models.workflow_run import WorkflowRun
from lib.services.workflow_runs import (
    get_workflow_run,
    get_workflow_run_state,
    get_workflow_run_state_by_thread_id,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_config_type, get_state_type
from lib.services.projects import create_project

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

# Register routers
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(evaluation.router)
app.include_router(workflows.router)
app.include_router(files.router)
app.include_router(feedback.router)
app.include_router(projects.router)


def create_start_workflow_handler(type: WorkflowRunType):
    ConfigType = get_config_type(type)

    async def handler(
        request: ConfigType,
        background_tasks: BackgroundTasks,
        user: User = Depends(get_current_user),
    ):
        # TODO: Remove this once we have a proper project creation flow and/or move the
        # reference downloader to tool inside a project
        if request.project_id is None and type == WorkflowRunType.REFERENCE_DOWNLOADER:
            project = await create_project(
                title=f"Reference Downloader {datetime.utcnow():%Y-%m-%d %H:%M UTC}",
                user=user,
            )
            request.project_id = str(project.id)

        workflow_run_id = await start_workflow_run(
            config=request, user=user, background_tasks=background_tasks
        )

        return StartWorkflowResponse(
            project_id=request.project_id,
            workflow_run_id=workflow_run_id,
            type=request.type,
            message=f"Workflow started. Track progress by polling the workflow result endpoint `/api/workflows/{type.value}/{workflow_run_id}`.",
        )

    return handler


def create_get_workflow_handler(type: WorkflowRunType, response_model: BaseModel):
    async def handler(workflow_run_id: str, user: User = Depends(get_current_user)):
        run = await get_workflow_run(workflow_run_id, user=user)
        state = await get_workflow_run_state_by_thread_id(
            run.langgraph_thread_id, run.type
        )
        return response_model(run=run, state=state)

    return handler


for run_type in WorkflowRunType:
    app.add_api_route(
        path=f"/api/workflows/{run_type.value}/start",
        methods=["POST"],
        tags=["workflows"],
        description=f'Start a workflow of type "{run_type.value}"',
        endpoint=create_start_workflow_handler(run_type),
        name=f"start_{run_type.value}_workflow",
        response_model=StartWorkflowResponse,
    )

    pascal_case_run_type = run_type.value.replace("_", " ").title().replace(" ", "")
    response_model = create_model(
        f"{pascal_case_run_type}WorkflowDetail",
        run=(WorkflowRun),
        state=(get_state_type(run_type, summary=True)),
    )

    app.add_api_route(
        path=f"/api/workflows/{run_type.value}/{{workflow_run_id}}",
        methods=["GET"],
        tags=["workflows"],
        description=f'Get the state of a workflow of type "{run_type.value}"',
        endpoint=create_get_workflow_handler(run_type, response_model),
        name=f"get_{run_type.value}_workflow_state",
        response_model=response_model,
    )
