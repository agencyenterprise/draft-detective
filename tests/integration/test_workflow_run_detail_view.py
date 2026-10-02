"""`GET /api/workflows/{id}`: one run with its state, for the owner or a share
token, with the transcript and the state each optional."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.api.routers.workflows import get_workflow_state
from lib.config.database import get_async_db_session
from lib.models.workflow_run import WorkflowRun
from lib.workflows.simple_deep_agent.state import SimpleDeepAgentState
from tests.integration.project_page_support import (  # noqa: F401  # `page` is a fixture
    RETIRED_TYPE,
    page,
)


async def _run_detail(page, **kwargs):
    args = {
        "include_state": True,
        "include_messages": True,
        "share_token": None,
        "current_user": page["owner"],
    }
    return await get_workflow_state(page["assessment_id"], **{**args, **kwargs})


@pytest.mark.asyncio
async def test_run_detail_carries_the_transcript_unless_asked_not_to(page):
    full = await _run_detail(page)
    without_messages = await _run_detail(page, include_messages=False)
    without_state = await _run_detail(page, include_state=False)

    assert isinstance(full.state, SimpleDeepAgentState)
    assert len(full.state.messages) == 3
    assert isinstance(without_messages.state, SimpleDeepAgentState)
    assert without_messages.state.messages == []
    assert without_state.state is None
    assert without_state.state_status == "ok"


@pytest.mark.asyncio
async def test_run_detail_honours_share_tokens_and_rejects_strangers(page):
    shared = await _run_detail(page, share_token=page["token"], current_user=None)
    assert shared.state is not None

    with pytest.raises(HTTPException) as exc:
        await _run_detail(page, current_user=page["stranger"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_run_detail_of_a_retired_workflow_is_404(page):
    async with get_async_db_session() as session:
        retired_id = (
            await session.execute(
                select(col(WorkflowRun.id)).where(
                    col(WorkflowRun.project_id) == uuid.UUID(page["project_id"]),
                    col(WorkflowRun.type) == RETIRED_TYPE,
                )
            )
        ).scalar_one()

    with pytest.raises(HTTPException) as exc:
        await get_workflow_state(
            str(retired_id),
            include_state=True,
            include_messages=True,
            share_token=None,
            current_user=page["owner"],
        )
    assert exc.value.status_code == 404
