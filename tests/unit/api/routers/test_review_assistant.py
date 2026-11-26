"""The Review Assistant endpoints: the access they demand and the order of the steps.

Starting a request needs write access and documents that belong to the
project, and both are checked before a run starts. A started run gets its
request recorded as soon as it is created, before it can be queued. Listing needs only read access. The services
have their own tests, so here they are stubbed and only the routing is under test.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import review_assistant
from lib.models.project import AccessLevel
from lib.models.user import User, UserRole
from lib.workflows.models import WorkflowRunType

CALLER = uuid.uuid4()
PROJECT = str(uuid.uuid4())
RUN = str(uuid.uuid4())
PATH = f"/api/project/{PROJECT}/review-assistant/requests"
MEMOS = "reviewer_response_memos"
SUMMARY = "revision_planning_summary"


def _client(signed_in: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(review_assistant.router)
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=CALLER,
            email="ana@example.com",
            name="Ana",
            role=UserRole.USER,
            show_experimental_features=False,
        )
    return TestClient(app, raise_server_exceptions=False)


async def _start_and_report_created(*, config, user, on_created) -> str:
    """As a start that creates the run: reports it before anything can queue it."""
    await on_created(RUN)
    return RUN


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Every call the routes make, on one parent mock so their order shows."""
    parent = MagicMock()
    stubs = {
        "get_project_access": AsyncMock(return_value=(MagicMock(), AccessLevel.WRITE)),
        "assert_project_files": AsyncMock(),
        "start_workflow_run": AsyncMock(side_effect=_start_and_report_created),
        "record_request": AsyncMock(),
        "list_review_assistant_requests": AsyncMock(return_value=[]),
    }
    for name, stub in stubs.items():
        parent.attach_mock(stub, name)
        monkeypatch.setattr(review_assistant, name, stub)
    return parent


def _start(
    files: list[str] | None = None, outputs: list[str] | None = None
) -> httpx2.Response:
    body = {"outputs": outputs or [MEMOS], "file_ids": files or ["f1"]}
    return _client().post(PATH, json=body)


def test_a_request_starts_with_its_repeats_dropped_and_is_recorded_on_its_run(
    steps: MagicMock,
) -> None:
    response = _start(files=["f1", "f2", "f1"], outputs=[MEMOS, SUMMARY, MEMOS])

    assert response.status_code == 200
    assert response.json() == {
        "project_id": PROJECT,
        "workflow_run_id": RUN,
        "type": WorkflowRunType.REVIEW_ASSISTANT.value,
        "message": "Review Assistant request started.",
    }
    assert [c[0] for c in steps.mock_calls] == [
        "get_project_access",
        "assert_project_files",
        "start_workflow_run",
        "record_request",
    ]
    config = steps.start_workflow_run.await_args.kwargs["config"]
    assert (config.project_id, config.input_file_ids) == (PROJECT, ["f1", "f2"])
    assert [o.value for o in config.outputs] == [MEMOS, SUMMARY]
    assert steps.start_workflow_run.await_args.kwargs["user"].id == CALLER
    steps.assert_project_files.assert_awaited_once_with(PROJECT, ["f1", "f2"])
    steps.record_request.assert_awaited_once_with(RUN, config)


def test_starting_a_request_needs_write_access(steps: MagicMock) -> None:
    steps.get_project_access.side_effect = HTTPException(status_code=403)

    response = _start()

    assert response.status_code == 403
    kwargs = steps.get_project_access.await_args.kwargs
    assert kwargs["required_level"] == AccessLevel.WRITE
    assert kwargs["user"].id == CALLER
    steps.start_workflow_run.assert_not_awaited()


def test_documents_outside_the_project_stop_the_run_before_it_starts(
    steps: MagicMock,
) -> None:
    steps.assert_project_files.side_effect = HTTPException(status_code=400)

    response = _start(files=["someone-elses"])

    assert response.status_code == 400
    steps.start_workflow_run.assert_not_awaited()
    steps.record_request.assert_not_awaited()


@pytest.mark.parametrize(
    "body",
    [
        {"outputs": [], "file_ids": ["f1"]},
        {"outputs": [MEMOS], "file_ids": []},
        {"outputs": ["a_poem"], "file_ids": ["f1"]},
    ],
    ids=["no-outputs", "no-files", "unknown-output"],
)
def test_an_empty_or_unknown_request_is_refused_before_any_lookup(
    steps: MagicMock, body: dict[str, list[str]]
) -> None:
    response = _client().post(PATH, json=body)

    assert response.status_code == 422
    assert steps.mock_calls == []


def test_listing_needs_read_access_only(steps: MagicMock) -> None:
    response = _client().get(PATH)

    assert response.status_code == 200
    kwargs = steps.get_project_access.await_args.kwargs
    assert kwargs.get("required_level", AccessLevel.READ) == AccessLevel.READ
    assert kwargs["user"].id == CALLER
    steps.list_review_assistant_requests.assert_awaited_once_with(PROJECT)


def test_a_project_the_caller_cannot_read_is_not_listed(steps: MagicMock) -> None:
    steps.get_project_access.side_effect = HTTPException(status_code=404)

    response = _client().get(PATH)

    assert response.status_code == 404
    steps.list_review_assistant_requests.assert_not_awaited()


def test_an_anonymous_request_is_refused(steps: MagicMock) -> None:
    client = _client(signed_in=False)

    statuses = (
        client.get(PATH).status_code,
        client.post(PATH, json={"outputs": [MEMOS], "file_ids": ["f1"]}).status_code,
    )

    assert statuses == (401, 401)
    assert steps.mock_calls == []
