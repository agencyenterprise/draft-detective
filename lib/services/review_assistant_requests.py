"""Review Assistant requests: starting one, and listing a project's past ones.

A request is a Review Assistant workflow run. Its outputs and documents live in
the run's config, so listing them reads that back. Requests are listed across
every revision: the documents a request reads are the files it names, not the
revision it happened to be started on.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.file import FileRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunPublic
from lib.services.files import get_files_by_project_id
from lib.services.project_overview import current_run_errors
from lib.services.uuid_utils import ensure_uuid
from lib.services.workflow_runs.service import persist_workflow_run_state
from lib.workflows.models import WorkflowError, WorkflowRunType
from lib.workflows.review_assistant.state import (
    ReviewAssistantConfig,
    ReviewAssistantOutput,
    ReviewAssistantState,
)

# What a request may read: anything a person uploaded to the project.
_READABLE_ROLES = [
    FileRole.MAIN,
    FileRole.SUPPORT,
    FileRole.REVIEWER_MEMO,
    FileRole.RESPONSE_MEMO,
    FileRole.REVIEW_INPUT,
]


class StartReviewAssistantRequest(BaseModel):
    outputs: list[ReviewAssistantOutput] = Field(min_length=1)
    file_ids: list[str] = Field(
        min_length=1, description="The documents to read, in the order to read them"
    )
    model: str | None = None


class ReviewAssistantRequestSummary(BaseModel):
    run: WorkflowRunPublic
    outputs: list[ReviewAssistantOutput]
    input_file_ids: list[str]
    errors: list[WorkflowError] = Field(
        default_factory=list,
        description="Errors recorded by this run itself, which can turn a completed run into a failed one",
    )


def request_config(
    project_id: str, request: StartReviewAssistantRequest
) -> ReviewAssistantConfig:
    """The run config for a request, with repeated outputs and files dropped."""
    return ReviewAssistantConfig(
        project_id=project_id,
        outputs=list(dict.fromkeys(request.outputs)),
        input_file_ids=list(dict.fromkeys(request.file_ids)),
        model=request.model,
    )


async def assert_project_files(project_id: str, file_ids: Sequence[str]) -> None:
    """400 unless every id is a document uploaded to this project."""
    files = await get_files_by_project_id(
        project_id,
        roles=_READABLE_ROLES,
        file_ids=[ensure_uuid(file_id, "file ID") for file_id in file_ids],
    )
    known = {str(file.id) for file in files}
    missing = [file_id for file_id in file_ids if file_id not in known]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"These files are not documents in this project: {', '.join(missing)}",
        )


async def record_request(workflow_run_id: str, config: ReviewAssistantConfig) -> None:
    """Store the request on its run straight away.

    The runner writes the run's state once it starts, which may be after the
    list is next read; until then the list would not know what was asked for.
    """
    await persist_workflow_run_state(
        workflow_run_id, ReviewAssistantState(config=config)
    )


def _summary(
    run: WorkflowRun, raw_config: Any, raw_errors: Any
) -> ReviewAssistantRequestSummary:
    config = ReviewAssistantConfig.model_validate(
        {**(raw_config or {}), "project_id": str(run.project_id)}
    )
    return ReviewAssistantRequestSummary(
        run=WorkflowRunPublic.model_validate(run),
        outputs=config.outputs,
        input_file_ids=config.input_file_ids,
        errors=current_run_errors(run.id, raw_errors),
    )


async def list_review_assistant_requests(
    project_id: str,
) -> list[ReviewAssistantRequestSummary]:
    """Every request on the project, newest first.

    Reads only the config and the errors out of each run's state, in SQL: the
    rest of it (the agent's transcript, the reports) is what the run view loads
    when one is opened, and the list is polled while a request runs.
    """
    state = col(WorkflowRun.state_json)
    stmt = (
        select(
            WorkflowRun,
            state["config"].label("config"),
            state["errors"].label("errors"),
        )
        .where(
            col(WorkflowRun.project_id) == uuid.UUID(project_id),
            col(WorkflowRun.type) == WorkflowRunType.REVIEW_ASSISTANT,
        )
        .order_by(col(WorkflowRun.created_at).desc())
    )
    async with get_async_db_session() as session:
        rows = (await session.execute(stmt)).all()
    return [
        _summary(run, raw_config, raw_errors) for run, raw_config, raw_errors in rows
    ]
