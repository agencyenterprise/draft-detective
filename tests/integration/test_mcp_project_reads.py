"""The MCP read tools return summaries, not full run states.

`get_project` (and `run_workflow`, which returns the same summary) carry each
run's status and errors plus the issues; `get_project_references` and
`get_workflow_run` return the parts of the states an agent asks for.
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.api.mcp.tools.projects import get_project, get_project_references
from lib.api.mcp.tools.workflows import get_workflow_run
from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.file import FileDocument
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from tests.integration.project_page_support import (  # noqa: F401  # `page` is a fixture
    RETIRED_TYPE,
    page,
)


def _as(user: Any):
    return patch("lib.api.mcp.helpers.resolve_user", new=AsyncMock(return_value=user))


async def _get_project(page: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    with _as(kwargs.pop("user", page["owner"])):
        return json.loads(
            await get_project(page["project_id"], token=MagicMock(), **kwargs)
        )


async def _get_run(page: dict[str, Any], run_id: str, **kwargs: Any) -> dict[str, Any]:
    with _as(kwargs.pop("user", page["owner"])):
        return json.loads(await get_workflow_run(run_id, token=MagicMock(), **kwargs))


@pytest.mark.asyncio
async def test_get_project_returns_run_summaries_and_live_issues(page):
    data = await _get_project(page)

    assert data["revision"] == 2
    assert data["access_level"] == "write"
    assert data["reference_count"] == 2
    assert data["project_url"].endswith(f"/projects/{page['project_id']}")
    assert [i["title"] for i in data["issues"]] == ["A finding"]
    runs = {r["run"]["type"]: r for r in data["workflow_runs"]}
    assert RETIRED_TYPE not in runs
    assert all("state" not in r and "state" not in r["run"] for r in runs.values())
    assert [e["error"] for e in runs["recommendation_check"]["errors"]] == ["mine"]
    # Files have their own tool; the share link and version only serve the page.
    for left_out in ("files", "share_status", "issues_version", "document"):
        assert left_out not in data


@pytest.mark.asyncio
async def test_get_project_includes_the_document_only_when_asked(page):
    data = await _get_project(page, include_document=True)

    assert data["document"]["title"] == "The Draft"
    assert data["document"]["authors"] == "A. Author"


@pytest.mark.asyncio
async def test_get_project_reads_an_older_revision(page):
    data = await _get_project(page, revision=1)

    assert data["revision"] == 1
    assert data["issues"] == []
    assert [r["run"]["type"] for r in data["workflow_runs"]] == ["recommendation_check"]


@pytest.mark.asyncio
async def test_get_project_rejects_strangers(page):
    with pytest.raises(HTTPException) as exc:
        await _get_project(page, user=page["stranger"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_project_references_returns_ids_matches_and_fetches(page):
    with _as(page["owner"]):
        data = json.loads(
            await get_project_references(page["project_id"], token=MagicMock())
        )

    assert [r["id"] for r in data["extracted_references"]] == ["r1", "r2"]
    assert [m["reference_id"] for m in data["matches"]] == ["r1"]
    (fetched,) = data["fetched_references"]
    assert fetched["reference_id"] == "r1"
    assert fetched.get("messages") in (None, [])


@pytest.mark.asyncio
async def test_get_workflow_run_leaves_the_transcript_out_unless_asked(page):
    default = await _get_run(page, page["assessment_id"])
    with_messages = await _get_run(page, page["assessment_id"], include_messages=True)

    assert default["run"]["id"] == page["assessment_id"]
    assert default["state"]["messages"] == []
    assert len(with_messages["state"]["messages"]) == 3
    assert "cost" in default


@pytest.mark.asyncio
async def test_get_workflow_run_rejects_strangers(page):
    with pytest.raises(HTTPException) as exc:
        await _get_run(page, page["assessment_id"], user=page["stranger"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_workflow_run_refuses_a_retired_workflow(page):
    async with get_async_db_session() as session:
        retired_id = (
            await session.execute(
                select(col(WorkflowRun.id)).where(
                    col(WorkflowRun.project_id) == uuid.UUID(page["project_id"]),
                    col(WorkflowRun.type) == RETIRED_TYPE,
                )
            )
        ).scalar_one()

    with pytest.raises(ValueError, match="no longer available"):
        await _get_run(page, str(retired_id))


def _converted(file_id: str) -> FileDocument:
    return FileDocument(
        file_id=file_id,
        file_name=f"{file_id}.md",
        file_path=f"/uploads/{file_id}.md",
        file_type="text/markdown",
        markdown=f"# {file_id} in full",
        markdown_token_count=1,
    )


@pytest.mark.asyncio
async def test_get_workflow_run_blanks_converted_documents(page):
    run_id = uuid.uuid4()
    state = DocumentProcessingState(
        config=DocumentProcessingWorkflowConfig(project_id=page["project_id"]),
        file=_converted("main"),
        supporting_files=[_converted("source")],
    )
    async with get_async_db_session() as session:
        session.add(
            WorkflowRun(
                id=run_id,
                project_id=uuid.UUID(page["project_id"]),
                type=WorkflowRunType.DOCUMENT_PROCESSING,
                langgraph_thread_id=str(uuid.uuid4()),
                status=WorkflowRunStatus.COMPLETED,
                revision=3,
                state_json=state.model_dump(mode="json"),
            )
        )
        await session.commit()

    data = await _get_run(page, str(run_id))

    assert data["state"]["file"]["markdown"] is None
    assert data["state"]["supporting_files"][0]["markdown"] is None
    assert "in full" not in json.dumps(data)
