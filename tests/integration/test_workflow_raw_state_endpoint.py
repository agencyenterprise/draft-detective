"""Authorization and payload contract for GET /api/workflows/{id}/raw-state.

The route is unusual on two counts: it bypasses the workflow's state model (that
is the point — it exists for runs whose persisted state no longer validates), and
it authenticates optionally so the escape hatch survives a share link. Neither is
covered by the hydration tests, so the contract is pinned here.
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import col

from lib.api.routers.workflows import get_workflow_raw_state
from lib.config.database import get_async_db_session
from lib.models.project import Project
from lib.models.share_link import ShareLink
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.workflows.models import WorkflowRunType

LIVE_TYPE = WorkflowRunType.RECOMMENDATION_CHECK
RETIRED_TYPE = "claim_substantiation"

# Deliberately not a valid state for LIVE_TYPE: the endpoint must hand back
# whatever is stored, without validating it.
STORED_STATE = {"type": LIVE_TYPE.value, "legacy_field": ["a", "b"], "n": 1}


@pytest_asyncio.fixture
async def fixtures():
    owner = User(
        id=uuid.uuid4(),
        email=f"raw-state-owner-{uuid.uuid4()}@example.com",
        name="Owner",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    stranger = User(
        id=uuid.uuid4(),
        email=f"raw-state-stranger-{uuid.uuid4()}@example.com",
        name="Stranger",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(
        id=uuid.uuid4(), user_id=owner.id, current_revision=1, title="raw-state test"
    )

    def _run(workflow_type: str) -> WorkflowRun:
        return WorkflowRun(
            id=uuid.uuid4(),
            project_id=project.id,
            type=workflow_type,  # type: ignore[arg-type]  # raw string is the retired-row case
            langgraph_thread_id=str(uuid.uuid4()),
            status=WorkflowRunStatus.COMPLETED,
            revision=1,
            state_json=STORED_STATE,
        )

    live_run, retired_run = _run(LIVE_TYPE.value), _run(RETIRED_TYPE)
    share = ShareLink(
        id=uuid.uuid4(),
        token=uuid.uuid4().hex,
        project_id=project.id,
        created_by_user_id=owner.id,
        is_active=True,
        created_at=datetime.now(UTC),
    )

    async with get_async_db_session() as session:
        session.add(owner)
        session.add(stranger)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(live_run)
        session.add(retired_run)
        session.add(share)
        await session.commit()

    yield {
        "owner": owner,
        "stranger": stranger,
        "project": project,
        "live_run": live_run,
        "retired_run": retired_run,
        "token": share.token,
    }

    async with get_async_db_session() as session:
        await session.execute(delete(ShareLink).where(col(ShareLink.id) == share.id))
        await session.execute(
            delete(WorkflowRun).where(col(WorkflowRun.project_id) == project.id)
        )
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(
            delete(User).where(col(User.id).in_([owner.id, stranger.id]))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_owner_gets_the_payload_verbatim(fixtures):
    """The stored JSON is returned untouched — no state-model validation."""
    result = await get_workflow_raw_state(
        workflow_run_id=str(fixtures["live_run"].id),
        share_token=None,
        current_user=fixtures["owner"],
    )

    assert result.state_json == STORED_STATE
    assert result.type == LIVE_TYPE.value  # the slug, not "WorkflowRunType.X"
    assert result.workflow_run_id == str(fixtures["live_run"].id)


@pytest.mark.asyncio
async def test_valid_share_token_authorizes_an_anonymous_viewer(fixtures):
    result = await get_workflow_raw_state(
        workflow_run_id=str(fixtures["live_run"].id),
        share_token=fixtures["token"],
        current_user=None,
    )

    assert result.state_json == STORED_STATE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "share_token, user_key",
    [
        (None, None),  # anonymous, no token
        ("not-a-real-token", None),  # anonymous, bogus token
        (None, "stranger"),  # authenticated, but not the owner
    ],
)
async def test_unauthorized_callers_are_rejected(fixtures, share_token, user_key):
    with pytest.raises(HTTPException) as exc:
        await get_workflow_raw_state(
            workflow_run_id=str(fixtures["live_run"].id),
            share_token=share_token,
            current_user=fixtures[user_key] if user_key else None,
        )

    assert exc.value.status_code in (403, 404)


@pytest.mark.asyncio
async def test_retired_workflow_type_is_404_even_for_the_owner(fixtures):
    """Retired runs are hidden everywhere else; this route must not be a way back in."""
    with pytest.raises(HTTPException) as exc:
        await get_workflow_raw_state(
            workflow_run_id=str(fixtures["retired_run"].id),
            share_token=None,
            current_user=fixtures["owner"],
        )

    assert exc.value.status_code == 404
