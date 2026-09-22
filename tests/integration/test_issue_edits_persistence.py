"""Proposed edits live in their own table, read back through their issue.

The relationship is `lazy="selectin"`, which this suite is what guards: the app
is fully async, so a lazy load outside an `await` raises `MissingGreenlet` at
serialization time rather than at query time. These tests exercise the three
places an `Issue` is handed back after a commit -- the rows returned by
`persist_workflow_issues`, a fresh read through `get_project_issues`, and the
`ProjectDetailed` payload -- and serialize each one.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlmodel import col

from lib.api.routers.issues import IssueResponse
from lib.config.database import get_async_db_session
from lib.models.issue import Issue
from lib.models.issue_edit import IssueEdit, IssueEditStatus
from lib.models.project import AccessLevel, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.issue_persistence import (
    get_project_issues,
    persist_workflow_issues,
    resolve_issue,
)
from lib.services.projects import ProjectDetailed
from lib.workflows.models import (
    DocumentIssue,
    ProposedEdit,
    SeverityEnum,
    WorkflowRunType,
)

WORKFLOW_TYPE = WorkflowRunType.FIGURES_TABLES_CHECK


def _document_issue() -> DocumentIssue:
    return DocumentIssue(
        title="Numbering mismatch",
        description="The body text cites Figure 3 but the caption reads Figure 2.",
        severity=SeverityEnum.MEDIUM,
        type=WORKFLOW_TYPE,
        start_line=6,
        end_line=8,
        edits=[
            ProposedEdit(
                original_text="**Figure 3**",
                replacement_text="**Figure 2**",
                start_line=6,
                end_line=6,
                rationale="Matches the caption.",
                display_text="Figure 3",
                display_occurrence=1,
                display_replacement="Figure 2",
            ),
            ProposedEdit(
                original_text="Figure 4",
                replacement_text="",
                start_line=8,
                end_line=8,
                rationale="Figure 4 does not exist.",
                display_text="Figure 4",
                display_occurrence=0,
                display_replacement="",
            ),
        ],
    )


@pytest_asyncio.fixture
async def persisted():
    """One project with a single issue carrying two proposed edits."""
    user = User(
        id=uuid.uuid4(),
        email=f"issue-edits-{uuid.uuid4()}@example.com",
        name="Test User",
        role=UserRole.USER,
        show_experimental_features=False,
    )
    project = Project(
        id=uuid.uuid4(), user_id=user.id, current_revision=1, title="issue edits"
    )
    run = WorkflowRun(
        id=uuid.uuid4(),
        project_id=project.id,
        type=WORKFLOW_TYPE,
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
        revision=1,
    )

    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()
    async with get_async_db_session() as session:
        session.add(run)
        await session.commit()

    created = await persist_workflow_issues(
        workflow_run_id=run.id,
        project_id=project.id,
        workflow_type=WORKFLOW_TYPE,
        issues=[_document_issue()],
        revision=1,
    )

    yield {"user": user, "project": project, "run": run, "created": created}

    async with get_async_db_session() as session:
        await session.execute(delete(Issue).where(col(Issue.project_id) == project.id))
        await session.execute(
            delete(WorkflowRun).where(col(WorkflowRun.project_id) == project.id)
        )
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


@pytest.mark.asyncio
async def test_persisted_issue_carries_its_edits_after_commit(persisted):
    """`persist_workflow_issues` refreshes each row; the edits must come back."""
    (issue,) = persisted["created"]

    assert [e.replacement_text for e in issue.edits] == ["**Figure 2**", ""]


@pytest.mark.asyncio
async def test_edits_are_read_back_ordered_by_position(persisted):
    (issue,) = await get_project_issues(persisted["project"].id, revision=1)

    assert [(e.original_text, e.replacement_text) for e in issue.edits] == [
        ("**Figure 3**", "**Figure 2**"),
        ("Figure 4", ""),
    ]
    # The rendered form the highlight and the export both read.
    assert [
        (e.display_text, e.display_occurrence, e.display_replacement)
        for e in issue.edits
    ] == [("Figure 3", 1, "Figure 2"), ("Figure 4", 0, "")]
    assert [e.start_line for e in issue.edits] == [6, 8]
    assert [e.rationale for e in issue.edits] == [
        "Matches the caption.",
        "Figure 4 does not exist.",
    ]
    assert all(e.status == IssueEditStatus.PROPOSED for e in issue.edits)
    assert all(e.issue_id == issue.id for e in issue.edits)


@pytest.mark.asyncio
async def test_rows_land_in_the_issue_edits_table_with_their_position(persisted):
    (issue,) = persisted["created"]

    async with get_async_db_session() as session:
        stmt = (
            select(IssueEdit)
            .where(col(IssueEdit.issue_id) == issue.id)
            .order_by(col(IssueEdit.position))
        )
        rows = (await session.execute(stmt)).scalars().all()

    assert [r.position for r in rows] == [0, 1]
    assert [r.original_text for r in rows] == ["**Figure 3**", "Figure 4"]
    assert [r.display_text for r in rows] == ["Figure 3", "Figure 4"]
    assert [r.display_occurrence for r in rows] == [1, 0]
    assert [r.display_replacement for r in rows] == ["Figure 2", ""]


@pytest.mark.asyncio
async def test_issue_response_publishes_the_edits(persisted):
    (issue,) = await get_project_issues(persisted["project"].id, revision=1)

    response = IssueResponse.from_model(issue)

    assert [e.replacement_text for e in response.edits] == ["**Figure 2**", ""]
    assert [e.display_text for e in response.edits] == ["Figure 3", "Figure 4"]
    assert response.edits[0].id == issue.edits[0].id


@pytest.mark.asyncio
async def test_project_detail_payload_serializes_the_edits(persisted):
    """The selectin path has to survive a full JSON dump of the detail payload."""
    issues = await get_project_issues(persisted["project"].id, revision=1)

    payload = ProjectDetailed(
        project=persisted["project"],
        access_level=AccessLevel.WRITE,
        issues=list(issues),
        revision=1,
    ).model_dump(mode="json")

    (serialized,) = payload["issues"]
    assert [e["replacement_text"] for e in serialized["edits"]] == [
        "**Figure 2**",
        "",
    ]
    assert serialized["edits"][0]["display_text"] == "Figure 3"
    assert serialized["edits"][0]["display_occurrence"] == 1
    assert serialized["edits"][0]["status"] == "proposed"
    assert serialized["edits"][0]["rationale"] == "Matches the caption."


@pytest.mark.asyncio
async def test_deleting_the_issue_deletes_its_edits(persisted):
    (issue,) = persisted["created"]

    async with get_async_db_session() as session:
        await session.execute(delete(Issue).where(col(Issue.id) == issue.id))
        await session.commit()

    async with get_async_db_session() as session:
        stmt = select(IssueEdit).where(col(IssueEdit.issue_id) == issue.id)
        assert (await session.execute(stmt)).scalars().all() == []


@pytest.mark.asyncio
async def test_resolving_an_issue_still_returns_its_edits(persisted):
    """`resolve_issue` commits and refreshes; the response serializes edits."""
    (created,) = persisted["created"]

    issue = await resolve_issue(created.id, persisted["user"].id)

    assert issue is not None
    assert [e.replacement_text for e in IssueResponse.from_model(issue).edits] == [
        "**Figure 2**",
        "",
    ]
