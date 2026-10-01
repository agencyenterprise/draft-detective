"""Contract for the project page's split reads.

The page used to load one `ProjectDetailed` holding every run's full state. It
now polls `/overview`, which must carry what the chrome reads (each run's own
errors, the reference count, whether the main file is Word) and no state, and
fetches the rest from `/document`, `/issues`, `/references`, the run history
and the run itself. These tests pin what each returns and who may read it.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import delete, select, update
from sqlmodel import col

from lib.api.routers.project_views import (
    get_project_document_endpoint,
    get_project_issues_endpoint,
    get_project_overview_endpoint,
    get_project_references_endpoint,
    get_project_workflow_runs_by_type_endpoint,
)
from lib.api.routers.public import get_shared_resource
from lib.api.routers.workflows import get_workflow_state
from lib.config.database import get_async_db_session
from lib.models.issue import Issue, IssueStatus
from lib.models.project import AccessLevel, Project
from lib.models.share_link import ShareLink
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.workflows.models import SeverityEnum, WorkflowError, WorkflowRunType
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
    ReferenceFetchResult,
    ReferenceFetchStatus,
)
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.simple_deep_agent.state import (
    SimpleDeepAgentConfig,
    SimpleDeepAgentState,
)

ASSESSMENT = WorkflowRunType.RECOMMENDATION_CHECK
# A workflow that no longer exists: its rows linger but must never surface.
RETIRED_TYPE = "claim_substantiation"


def _user(label: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"page-views-{label}-{uuid.uuid4()}@example.com",
        name=label,
        role=UserRole.USER,
        show_experimental_features=False,
    )


def _run(
    project_id: uuid.UUID,
    workflow_type: WorkflowRunType | str,
    state_json: dict[str, Any],
    run_id: uuid.UUID | None = None,
    revision: int = 1,
    created_at: datetime | None = None,
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id or uuid.uuid4(),
        project_id=project_id,
        type=workflow_type,  # type: ignore[arg-type]  # a str only for retired rows
        langgraph_thread_id=str(uuid.uuid4()),
        status=WorkflowRunStatus.COMPLETED,
        revision=revision,
        state_json=state_json,
        created_at=created_at or datetime.now(UTC),
    )


def _assessment_state(project_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    return SimpleDeepAgentState(
        type=ASSESSMENT,
        config=SimpleDeepAgentConfig(type=ASSESSMENT, project_id=str(project_id)),
        messages=[
            HumanMessage(content="Check the recommendations."),
            ToolMessage(content="tool output", tool_call_id="call-1"),
            AIMessage(content="Done."),
        ],
        errors=[
            WorkflowError(task_name="t", error="mine", workflow_run_id=str(run_id)),
            # An earlier run on the same thread: not this run's error.
            WorkflowError(task_name="t", error="theirs", workflow_run_id="older"),
        ],
    ).model_dump(mode="json")


def _extraction_state(project_id: uuid.UUID) -> dict[str, Any]:
    return ReferenceExtractionState(
        type=WorkflowRunType.REFERENCE_EXTRACTION,
        config=ReferenceExtractionConfig(
            type=WorkflowRunType.REFERENCE_EXTRACTION, project_id=str(project_id)
        ),
        file_id="main",
        extracted_references=[
            ExtractedReference(id="r1", text="Smith 2020"),
            ExtractedReference(id="r2", text="Jones 2021"),
        ],
        reasoning="",
        messages=[HumanMessage(content="Extract.")],
    ).model_dump(mode="json")


def _downloader_state(project_id: uuid.UUID) -> dict[str, Any]:
    return ReferenceDownloaderState(
        type=WorkflowRunType.REFERENCE_DOWNLOADER,
        config=ReferenceDownloaderWorkflowConfig(
            type=WorkflowRunType.REFERENCE_DOWNLOADER,
            project_id=str(project_id),
            references=[],
        ),
        fetched_references=[
            ReferenceFetchResult(
                reference_id="r1",
                input_reference="Smith 2020",
                status=ReferenceFetchStatus.COMPLETED,
                messages=[HumanMessage(content="Find Smith 2020.")],
            )
        ],
    ).model_dump(mode="json")


@pytest_asyncio.fixture
async def page():
    owner, stranger = _user("owner"), _user("stranger")
    project = Project(
        id=uuid.uuid4(), user_id=owner.id, current_revision=2, title="views"
    )
    now = datetime.now(UTC)
    assessment_id = uuid.uuid4()
    runs = [
        _run(
            project.id,
            ASSESSMENT,
            _assessment_state(project.id, assessment_id),
            run_id=assessment_id,
            revision=2,
            created_at=now,
        ),
        # An older run of the same assessment, for the history.
        _run(
            project.id,
            ASSESSMENT,
            _assessment_state(project.id, uuid.uuid4()),
            revision=2,
            created_at=now.replace(year=now.year - 1),
        ),
        # The same assessment on another revision: never in revision 2's history.
        _run(project.id, ASSESSMENT, {"type": ASSESSMENT.value}, revision=1),
        _run(
            project.id,
            WorkflowRunType.REFERENCE_EXTRACTION,
            _extraction_state(project.id),
            revision=2,
        ),
        _run(
            project.id,
            WorkflowRunType.REFERENCE_DOWNLOADER,
            _downloader_state(project.id),
            revision=2,
        ),
        _run(
            project.id,
            WorkflowRunType.DOCUMENT_PROCESSING,
            {"type": "document_processing", "file": {"file_path": "up/Main.DOCX"}},
            revision=2,
        ),
        _run(
            project.id,
            WorkflowRunType.REFERENCE_FILE_MATCHING,
            {
                "type": "reference_file_matching",
                "matches": [
                    {"reference_id": "r1", "file_id": "f1", "source": "manual_upload"},
                    {"reference_id": "r2"},  # unreadable: no file, no source
                ],
            },
            revision=2,
        ),
        _run(
            project.id,
            RETIRED_TYPE,  # type: ignore[arg-type]  # raw string is the retired-row case
            {"type": RETIRED_TYPE, "errors": []},
            revision=2,
        ),
        _run(
            project.id,
            WorkflowRunType.DOCUMENT_SUMMARIZATION,
            {
                "type": "document_summarization",
                "main_file_id": "main",
                "summaries": [
                    {"file_id": "support", "title": "A source", "authors": "X"},
                    {"file_id": "main", "title": "The Draft", "authors": "A. Author"},
                ],
            },
            revision=2,
        ),
    ]
    issue = Issue(
        id=uuid.uuid4(),
        project_id=project.id,
        workflow_run_id=assessment_id,
        issue_hash=uuid.uuid4().hex,
        title="A finding",
        description="Something to fix",
        severity=SeverityEnum.HIGH,
        workflow_type=ASSESSMENT,
        revision=2,
    )
    archived = Issue(
        id=uuid.uuid4(),
        project_id=project.id,
        workflow_run_id=assessment_id,
        issue_hash=uuid.uuid4().hex,
        title="An archived finding",
        description="From before the last re-run",
        severity=SeverityEnum.LOW,
        workflow_type=ASSESSMENT,
        revision=2,
        status=IssueStatus.ARCHIVED,
    )

    def _share(resource_type: str) -> ShareLink:
        return ShareLink(
            id=uuid.uuid4(),
            token=uuid.uuid4().hex,
            resource_type=resource_type,
            resource_id=project.id,
            created_by_user_id=owner.id,
            is_active=True,
            created_at=now,
        )

    share, other_share = _share("project"), _share("workflow_run")

    async with get_async_db_session() as session:
        session.add_all([owner, stranger])
        await session.commit()
    async with get_async_db_session() as session:
        session.add(project)
        await session.commit()
    async with get_async_db_session() as session:
        session.add_all([*runs, share, other_share])
        await session.commit()
    async with get_async_db_session() as session:
        session.add_all([issue, archived])
        await session.commit()

    yield {
        "owner": owner,
        "stranger": stranger,
        "project_id": str(project.id),
        "assessment_id": str(assessment_id),
        "issue_id": issue.id,
        "token": share.token,
        "share_id": share.id,
        "other_token": other_share.token,
    }

    async with get_async_db_session() as session:
        await session.execute(
            delete(ShareLink).where(col(ShareLink.id).in_([share.id, other_share.id]))
        )
        # Deleting the project cascades to its runs and issues.
        await session.execute(delete(Project).where(col(Project.id) == project.id))
        await session.execute(
            delete(User).where(col(User.id).in_([owner.id, stranger.id]))
        )
        await session.commit()


async def _overview(page, **kwargs):
    args = {"revision": None, "share_token": None, "current_user": page["owner"]}
    return await get_project_overview_endpoint(page["project_id"], **{**args, **kwargs})


@pytest.mark.asyncio
async def test_overview_carries_what_the_chrome_reads_and_no_state(page):
    overview = await _overview(page)

    assert overview.access_level == AccessLevel.WRITE
    assert overview.revision == 2
    assert overview.reference_count == 2
    assert overview.has_docx is True
    # One run per type, the latest of the assessment.
    types = [summary.run.type for summary in overview.workflow_runs]
    assert sorted(types) == sorted(set(types))
    assessment = next(s for s in overview.workflow_runs if s.run.type == ASSESSMENT)
    assert str(assessment.run.id) == page["assessment_id"]
    assert [error.error for error in assessment.errors] == ["mine"]
    assert "state" not in overview.model_dump()["workflow_runs"][0]


@pytest.mark.asyncio
async def test_issues_version_moves_when_an_issue_changes(page):
    before = (await _overview(page)).issues_version

    async with get_async_db_session() as session:
        await session.execute(
            update(Issue)
            .where(col(Issue.id) == page["issue_id"])
            .values(resolved_at=datetime.now(UTC))
        )
        await session.commit()

    assert (await _overview(page)).issues_version != before


@pytest.mark.asyncio
async def test_overview_follows_the_revision_asked_for(page):
    overview = await _overview(page, revision=1)

    assert overview.revision == 1
    assert [s.run.type for s in overview.workflow_runs] == [ASSESSMENT]
    assert overview.reference_count == 0


@pytest.mark.asyncio
async def test_share_token_reads_and_strangers_do_not(page):
    shared = await _overview(page, share_token=page["token"], current_user=None)
    assert shared.access_level == AccessLevel.READ

    with pytest.raises(HTTPException) as exc:
        await _overview(page, current_user=page["stranger"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_public_share_is_read_only_overview(page):
    overview = await get_shared_resource(page["token"])

    assert overview.access_level == AccessLevel.READ
    assert str(overview.project.id) == page["project_id"]
    # The link is the owner's to manage; whoever holds it is not shown it.
    assert overview.share_status is None


@pytest.mark.asyncio
async def test_only_the_owner_sees_the_share_status(page):
    owned = await _overview(page)
    shared = await _overview(page, share_token=page["token"], current_user=None)

    assert owned.share_status is not None
    assert owned.share_status.enabled is True
    assert owned.share_status.share_link is not None
    assert owned.share_status.share_link.token == page["token"]
    assert shared.share_status is None


@pytest.mark.asyncio
async def test_document_takes_title_and_authors_from_the_main_file_summary(page):
    document = await get_project_document_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert (document.title, document.authors) == ("The Draft", "A. Author")
    assert document.markdown is None  # no main file on record in this fixture


@pytest.mark.asyncio
async def test_issues_are_the_revisions_own(page):
    current = await get_project_issues_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )
    older = await get_project_issues_endpoint(
        page["project_id"], revision=1, share_token=None, current_user=page["owner"]
    )

    assert [issue.id for issue in current] == [page["issue_id"]]
    assert older == []


@pytest.mark.asyncio
async def test_references_drop_the_fetch_transcripts(page):
    references = await get_project_references_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert [ref.id for ref in references.extracted_references] == ["r1", "r2"]
    assert [f.reference_id for f in references.fetched_references] == ["r1"]
    assert references.fetched_references[0].messages == []


@pytest.mark.asyncio
async def test_history_lists_the_revisions_runs_newest_first(page):
    history = await get_project_workflow_runs_by_type_endpoint(
        page["project_id"],
        workflow_type=ASSESSMENT,
        revision=None,
        share_token=None,
        current_user=page["owner"],
    )

    assert len(history) == 2
    assert str(history[0].run.id) == page["assessment_id"]
    assert history[0].run.created_at > history[1].run.created_at


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
async def test_overview_never_surfaces_retired_workflows(page):
    overview = await _overview(page)

    assert RETIRED_TYPE not in [str(s.run.type) for s in overview.workflow_runs]
    assert all(isinstance(s.run.type, WorkflowRunType) for s in overview.workflow_runs)


@pytest.mark.asyncio
async def test_a_revision_without_processing_is_not_word(page):
    assert (await _overview(page, revision=1)).has_docx is False


@pytest.mark.asyncio
async def test_archived_issues_are_neither_listed_nor_counted(page):
    issues = await get_project_issues_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )
    overview = await _overview(page)

    assert [issue.id for issue in issues] == [page["issue_id"]]
    assert overview.issues_version.startswith("1:")


@pytest.mark.asyncio
async def test_references_keep_the_readable_matches(page):
    references = await get_project_references_endpoint(
        page["project_id"], revision=None, share_token=None, current_user=page["owner"]
    )

    assert [(m.reference_id, m.file_id) for m in references.matches] == [("r1", "f1")]


@pytest.mark.asyncio
async def test_document_reads_the_revisions_markdown(page):
    with patch(
        "lib.services.project_content.get_main_document_markdown",
        new=AsyncMock(return_value="# The Draft"),
    ) as markdown:
        document = await get_project_document_endpoint(
            page["project_id"], revision=1, share_token=None, current_user=page["owner"]
        )

    markdown.assert_awaited_once_with(page["project_id"], 1)
    assert document.markdown == "# The Draft"
    # Revision 1 was never summarized, so there is no title to show.
    assert (document.title, document.authors) == (None, None)


@pytest.mark.asyncio
async def test_history_follows_the_revision_asked_for(page):
    history = await get_project_workflow_runs_by_type_endpoint(
        page["project_id"],
        workflow_type=ASSESSMENT,
        revision=1,
        share_token=None,
        current_user=page["owner"],
    )

    assert len(history) == 1
    assert history[0].run.revision == 1


@pytest.mark.asyncio
async def test_share_status_reports_a_disabled_link(page):
    async with get_async_db_session() as session:
        await session.execute(
            update(ShareLink)
            .where(col(ShareLink.id) == page["share_id"])
            .values(is_active=False)
        )
        await session.commit()

    overview = await _overview(page)

    assert overview.share_status is not None
    assert overview.share_status.enabled is False
    assert overview.share_status.share_link is None


@pytest.mark.asyncio
async def test_public_share_rejects_unknown_and_disabled_links(page):
    with pytest.raises(HTTPException) as unknown:
        await get_shared_resource("not-a-real-token")
    assert unknown.value.status_code == 404

    async with get_async_db_session() as session:
        await session.execute(
            update(ShareLink)
            .where(col(ShareLink.id) == page["share_id"])
            .values(is_active=False)
        )
        await session.commit()

    with pytest.raises(HTTPException) as disabled:
        await get_shared_resource(page["token"])
    assert disabled.value.status_code == 404


@pytest.mark.asyncio
async def test_public_share_serves_only_projects(page):
    with pytest.raises(HTTPException) as exc:
        await get_shared_resource(page["other_token"])
    assert exc.value.status_code == 400


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
