"""Retired workflows must not reach a client through any read path.

Rows outlive the workflows that wrote them: `workflow_runs.type` and
`issues.workflow_type` keep whatever slug was current when they were written,
and nothing rewrites them when a workflow is removed. Three read paths have to
exclude them, and each has its own way of getting it wrong:

- `get_project_issues` — issues have no run to open and no manifest to name
  them, so they would render under a raw slug.
- `get_project_workflow_runs` — `include_internal=True` is passed by the public
  share response and the MCP serializer, so it cannot be a back door.
- `get_user_projects` — filters in the join, where an over-eager predicate on
  the right-hand table would turn the outer join into an inner one.
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.issue import Issue, IssueStatus
from lib.models.project import Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.issue_persistence import get_project_issues
from lib.services.projects import get_user_projects
from lib.services.workflow_runs.service import get_project_workflow_runs
from lib.workflows.models import SeverityEnum, WorkflowRunType

# Removed in an earlier cleanup; rows carrying it are still in the database.
RETIRED_TYPE = "claim_substantiation"
LIVE_TYPE = WorkflowRunType.RECOMMENDATION_CHECK


def _run(project_id: uuid.UUID, workflow_type: str) -> WorkflowRun:
    return WorkflowRun(
        id=uuid.uuid4(),
        project_id=project_id,
        type=workflow_type,  # type: ignore[arg-type]  # raw string is exactly the retired-row case
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
        revision=1,
    )


def _issue(project_id: uuid.UUID, run: WorkflowRun, title: str) -> Issue:
    now = datetime.now(UTC)
    return Issue(
        id=uuid.uuid4(),
        project_id=project_id,
        workflow_run_id=run.id,
        issue_hash=str(uuid.uuid4()),
        revision=1,
        title=title,
        description="d",
        severity=SeverityEnum.LOW,
        workflow_type=run.type,
        status=IssueStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def scenario():
    """One user with two projects: a mixed one, and one that is retired-only.

    The retired-only project is the interesting case for the project list — it
    must still be listed, with an empty run list, rather than disappearing.
    """
    user = User(
        id=uuid.uuid4(),
        email=f"retired-wf-{uuid.uuid4()}@example.com",
        name="Test User",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    mixed = Project(id=uuid.uuid4(), user_id=user.id, current_revision=1, title="mixed")
    retired_only = Project(
        id=uuid.uuid4(), user_id=user.id, current_revision=1, title="retired only"
    )

    mixed_retired = _run(mixed.id, RETIRED_TYPE)
    mixed_live = _run(mixed.id, LIVE_TYPE.value)
    orphan_run = _run(retired_only.id, RETIRED_TYPE)

    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(mixed)
        session.add(retired_only)
        await session.commit()
    async with get_async_db_session() as session:
        for run in (mixed_retired, mixed_live, orphan_run):
            session.add(run)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(_issue(mixed.id, mixed_retired, "from a retired workflow"))
        session.add(_issue(mixed.id, mixed_live, "from a live workflow"))
        await session.commit()

    yield {"user": user, "mixed": mixed, "retired_only": retired_only}

    project_ids = [mixed.id, retired_only.id]
    async with get_async_db_session() as session:
        await session.execute(
            delete(Issue).where(col(Issue.project_id).in_(project_ids))
        )
        await session.execute(
            delete(WorkflowRun).where(col(WorkflowRun.project_id).in_(project_ids))
        )
        await session.execute(delete(Project).where(col(Project.id).in_(project_ids)))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


# --------------------------------------------------------------------------
# Issues
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issues_from_retired_workflows_are_not_returned(scenario):
    issues = await get_project_issues(scenario["mixed"].id, revision=1)

    assert {i.title for i in issues} == {"from a live workflow"}


@pytest.mark.asyncio
async def test_the_retired_issue_row_still_exists(scenario):
    """Filtered from the API, not deleted — the row stays recoverable."""
    async with get_async_db_session() as session:
        stmt = select(Issue).where(
            col(Issue.project_id) == scenario["mixed"].id,
            col(Issue.workflow_type) == RETIRED_TYPE,
        )
        assert (await session.execute(stmt)).scalar_one_or_none() is not None


# --------------------------------------------------------------------------
# Workflow runs
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("include_internal", [False, True])
async def test_retired_runs_are_hidden_from_the_detail_path(scenario, include_internal):
    """`include_internal=True` must not be a back door.

    The public share response and the MCP project serializer both pass it, so a
    filter that only applied to the user-facing listing would still hand retired
    workflows to those clients.
    """
    runs = await get_project_workflow_runs(
        str(scenario["mixed"].id), revision=1, include_internal=include_internal
    )

    assert all(str(r.run.type) != RETIRED_TYPE for r in runs)


# --------------------------------------------------------------------------
# Project list
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_list_excludes_retired_runs(scenario):
    items = (await get_user_projects(scenario["user"])).items

    by_id = {item.project.id: item for item in items}
    mixed = by_id[scenario["mixed"].id]

    assert [str(r.type) for r in mixed.workflow_runs] == [LIVE_TYPE.value]


@pytest.mark.asyncio
async def test_project_list_keeps_a_project_whose_runs_are_all_retired(scenario):
    """The join-vs-WHERE trap.

    Filtering retired types in the WHERE clause instead of the join condition
    turns the outer join into an inner one, and a project whose every run is
    retired vanishes from the user's project list entirely.
    """
    items = (await get_user_projects(scenario["user"])).items

    by_id = {item.project.id: item for item in items}
    assert scenario["retired_only"].id in by_id, "project disappeared from the list"
    assert by_id[scenario["retired_only"].id].workflow_runs == []


@pytest.mark.asyncio
async def test_project_list_pages_and_searches_server_side(scenario):
    user = scenario["user"]

    first = await get_user_projects(user, limit=1, offset=0)
    second = await get_user_projects(user, limit=1, offset=1)
    assert first.total == second.total == 2
    assert len(first.items) == len(second.items) == 1
    assert first.items[0].project.id != second.items[0].project.id

    matched = await get_user_projects(user, search="RETIRED only")
    assert matched.total == 1
    assert matched.items[0].project.id == scenario["retired_only"].id
    assert matched.items[0].workflow_runs == []


@pytest.mark.asyncio
async def test_project_list_clamps_out_of_range_paging(scenario):
    """A limit of 0 would otherwise reach Postgres as an unbounded LIMIT."""
    page = await get_user_projects(scenario["user"], limit=0, offset=-5)

    assert (page.limit, page.offset) == (1, 0)
    assert len(page.items) == 1
