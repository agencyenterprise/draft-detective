"""Unit tests for the admin feedback CSV export endpoint."""

import csv
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue, IssueStatus
from lib.models.project import FeedbackVisibility, Project
from lib.models.user import User, UserRole
from lib.models.workflow_run import WorkflowRunType
from lib.workflows.models import SeverityEnum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_user(**kwargs) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        name="Alice",
        role=UserRole.USER,
        show_experimental_features=False,
        created_at=_NOW,
        last_updated_at=_NOW,
    )
    return User(**{**defaults, **kwargs})


def _make_project(**kwargs) -> Project:
    defaults = dict(
        id=uuid.uuid4(),
        title="My Project",
        user_id=uuid.uuid4(),
        feedback_visibility=FeedbackVisibility.ISSUE_ONLY,
        created_at=_NOW,
        last_updated_at=_NOW,
    )
    return Project(**{**defaults, **kwargs})


def _make_issue(**kwargs) -> Issue:
    defaults = dict(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workflow_run_id=uuid.uuid4(),
        issue_hash=str(uuid.uuid4()),
        title="Issue Title",
        description="Short description.",
        long_description="Long description.",
        severity=SeverityEnum.HIGH,
        workflow_type=WorkflowRunType.CITATION_DETECTION,
        status=IssueStatus.ACTIVE,
        chunk_indices=[0, 2],
        created_at=_NOW,
        updated_at=_NOW,
    )
    return Issue(**{**defaults, **kwargs})


def _make_feedback(**kwargs) -> Feedback:
    defaults = dict(
        id=uuid.uuid4(),
        workflow_run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        issue_id=uuid.uuid4(),
        entity_path={},
        feedback_type=FeedbackType.THUMBS_DOWN,
        feedback_text="Not accurate.",
        created_at=_NOW,
        updated_at=_NOW,
    )
    return Feedback(**{**defaults, **kwargs})


def _parse_csv(response_body: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(response_body))
    return list(reader)


async def _read_streaming_response(response) -> str:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_headers():
    """The export response contains all expected column headers."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    reader = csv.reader(io.StringIO(body))
    headers = next(reader)

    assert headers == [
        "Feedback Date",
        "Feedback Type",
        "Feedback Text",
        "User ID",
        "User Name",
        "User Email",
        "Project ID",
        "Project Title",
        "Visibility",
        "Issue ID",
        "Issue Title",
        "Issue Description",
        "Issue Long Description",
        "Issue Severity",
        "Issue Workflow Type",
    ]


@pytest.mark.asyncio
async def test_csv_empty_returns_only_header():
    """When there is no feedback, the CSV contains only the header row."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    rows = _parse_csv(body)
    assert rows == []


@pytest.mark.asyncio
async def test_csv_row_values():
    """Each CSV row contains the correct values from the feedback data."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    user = _make_user(name="Bob", email="bob@example.com")
    project = _make_project(
        title="Report", feedback_visibility=FeedbackVisibility.FULL_PROJECT
    )
    issue = _make_issue(
        title="Wrong citation",
        description="The citation is incorrect.",
        long_description="Detailed explanation here.",
        severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CITATION_DETECTION,
            status=IssueStatus.ACTIVE,
            chunk_indices=[1, 3],
    )
    feedback = _make_feedback(
        feedback_type=FeedbackType.THUMBS_DOWN,
        feedback_text="This is wrong.",
        created_at=_NOW,
    )

    mock_rows = [
        {"feedback": feedback, "issue": issue, "project": project, "user": user}
    ]

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=mock_rows),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    rows = _parse_csv(body)

    assert len(rows) == 1
    row = rows[0]

    assert row["Feedback Date"] == _NOW.isoformat()
    assert row["Feedback Type"] == FeedbackType.THUMBS_DOWN.value
    assert row["Feedback Text"] == "This is wrong."
    assert row["User ID"] == str(user.id)
    assert row["User Name"] == "Bob"
    assert row["User Email"] == "bob@example.com"
    assert row["Project ID"] == str(project.id)
    assert row["Project Title"] == "Report"
    assert row["Visibility"] == FeedbackVisibility.FULL_PROJECT.value
    assert row["Issue ID"] == str(issue.id)
    assert row["Issue Title"] == "Wrong citation"
    assert row["Issue Description"] == "The citation is incorrect."
    assert row["Issue Long Description"] == "Detailed explanation here."
    assert row["Issue Severity"] == SeverityEnum.MEDIUM.value
    assert row["Issue Workflow Type"] == WorkflowRunType.CITATION_DETECTION.value


@pytest.mark.asyncio
async def test_csv_empty_feedback_text():
    """Feedback with no text produces an empty string in the CSV, not 'None'."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    feedback = _make_feedback(feedback_type=FeedbackType.THUMBS_UP, feedback_text=None)
    mock_rows = [
        {
            "feedback": feedback,
            "issue": _make_issue(),
            "project": _make_project(),
            "user": _make_user(),
        }
    ]

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=mock_rows),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    rows = _parse_csv(body)

    assert rows[0]["Feedback Text"] == ""


@pytest.mark.asyncio
async def test_csv_no_extra_columns():
    """The CSV does not include removed columns (Status, Chunk Indices, Created At)."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    reader = csv.reader(io.StringIO(body))
    headers = next(reader)

    assert "Issue Status" not in headers
    assert "Issue Chunk Indices" not in headers
    assert "Issue Created At" not in headers


@pytest.mark.asyncio
async def test_csv_multiple_rows_ordered():
    """Multiple feedback rows are all written to the CSV."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    rows_data = [
        {
            "feedback": _make_feedback(feedback_type=FeedbackType.THUMBS_UP),
            "issue": _make_issue(title="Issue A"),
            "project": _make_project(title="Project A"),
            "user": _make_user(name="Alice"),
        },
        {
            "feedback": _make_feedback(feedback_type=FeedbackType.THUMBS_DOWN),
            "issue": _make_issue(title="Issue B"),
            "project": _make_project(title="Project B"),
            "user": _make_user(name="Bob"),
        },
    ]

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=rows_data),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    body = await _read_streaming_response(response)
    rows = _parse_csv(body)

    assert len(rows) == 2
    assert rows[0]["Issue Title"] == "Issue A"
    assert rows[1]["Issue Title"] == "Issue B"


@pytest.mark.asyncio
async def test_csv_response_headers():
    """StreamingResponse has the correct content-type and content-disposition."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ):
        response = await export_admin_feedbacks_csv(workflow_type=None)

    assert response.media_type == "text/csv"
    assert response.headers["content-disposition"] == "attachment; filename=feedbacks.csv"


# ---------------------------------------------------------------------------
# Pagination forwarding tests (GET /api/admin/feedbacks)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_feedbacks_default_pagination():
    """Default limit=25 and offset=0 are forwarded to the service."""
    from lib.api.routers.feedback import get_admin_feedbacks

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await get_admin_feedbacks(limit=25, offset=0, workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["limit"] == 25
    assert call_kwargs["offset"] == 0


@pytest.mark.asyncio
async def test_admin_feedbacks_custom_pagination():
    """Custom limit and offset values are forwarded to the service."""
    from lib.api.routers.feedback import get_admin_feedbacks

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await get_admin_feedbacks(limit=10, offset=50, workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["limit"] == 10
    assert call_kwargs["offset"] == 50


@pytest.mark.asyncio
async def test_csv_export_does_not_pass_pagination():
    """CSV export endpoint does NOT forward limit/offset (always exports all results)."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await export_admin_feedbacks_csv(workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert "limit" not in call_kwargs
    assert "offset" not in call_kwargs


# ---------------------------------------------------------------------------
# Search forwarding tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_forwarded_to_service():
    """search param is forwarded to the service when provided."""
    from lib.api.routers.feedback import get_admin_feedbacks

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await get_admin_feedbacks(search="climate", workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["search"] == "climate"


@pytest.mark.asyncio
async def test_search_default_is_none():
    """search defaults to None when not provided."""
    from lib.api.routers.feedback import get_admin_feedbacks

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await get_admin_feedbacks(search=None, workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["search"] is None


@pytest.mark.asyncio
async def test_csv_export_search_forwarded_to_service():
    """CSV export forwards the search param to the service."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await export_admin_feedbacks_csv(search="climate", workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["search"] == "climate"


@pytest.mark.asyncio
async def test_csv_export_search_default_is_none():
    """CSV export search defaults to None when not provided."""
    from lib.api.routers.feedback import export_admin_feedbacks_csv

    with patch(
        "lib.api.routers.feedback.feedback_service.get_admin_feedbacks",
        new=AsyncMock(return_value=[]),
    ) as mock_service:
        await export_admin_feedbacks_csv(search=None, workflow_type=None)

    call_kwargs = mock_service.call_args.kwargs
    assert call_kwargs["search"] is None
