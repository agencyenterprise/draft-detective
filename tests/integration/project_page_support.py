"""The project shared by the project-page view tests.

One revision-2 project with an assessment and an older run of it, the
reference runs, processing and summarization, a retired workflow's run, one
live and one archived issue, and two share links (a project one and one for
another kind of resource), owned by `owner` and invisible to `stranger`.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator

import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import delete, update
from sqlmodel import col

from lib.api.routers.project_views import get_project_overview_endpoint
from lib.config.database import get_async_db_session
from lib.models.issue import Issue, IssueStatus
from lib.models.project import Project
from lib.models.share_link import ShareLink
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRun, WorkflowRunStatus
from lib.services.project_overview import ProjectOverview
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
async def page() -> AsyncIterator[dict[str, Any]]:
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


async def overview_of(page: dict[str, Any], **kwargs: Any) -> ProjectOverview:
    """The overview as the owner reads it, unless `kwargs` say otherwise."""
    args = {"revision": None, "share_token": None, "current_user": page["owner"]}
    return await get_project_overview_endpoint(page["project_id"], **{**args, **kwargs})


async def disable_share_link(page: dict[str, Any]) -> None:
    async with get_async_db_session() as session:
        await session.execute(
            update(ShareLink)
            .where(col(ShareLink.id) == page["share_id"])
            .values(is_active=False)
        )
        await session.commit()
