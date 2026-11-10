"""The workflow-type endpoints: who may call them, and what they require.

The listing is static config and public. The recent selection is per-user, so
it needs a signed-in caller. The duration estimates need a `project_id`; their
cache is pinned in test_workflow_types_duration_estimates.py. Whether an
anonymous caller may read the estimates is left unpinned: the route allows it
today, and that is an open question rather than settled behaviour.
The services have their own integration tests and are stubbed here.
"""

import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import workflow_types
from lib.models.user import User, UserRole
from lib.services.workflow_duration_estimates import WorkflowDurationEstimatesResponse
from lib.services.workflow_types import RecentWorkflowSelectionResponse

CALLER = uuid.uuid4()


def _client(signed_in: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(workflow_types.router)
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: User(
            id=CALLER,
            email="ana@example.com",
            name="Ana",
            role=UserRole.USER,
            show_experimental_features=False,
        )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def estimates(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    """The estimates service, behind an empty cache that is emptied again after."""
    stub = AsyncMock(return_value=WorkflowDurationEstimatesResponse(estimates=[]))
    monkeypatch.setattr(workflow_types, "get_workflow_duration_estimates", stub)
    workflow_types._cached_duration_estimates.cache_clear()
    yield stub
    workflow_types._cached_duration_estimates.cache_clear()


def test_the_listing_needs_no_sign_in(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = MagicMock(wraps=workflow_types.get_all_workflow_types)
    monkeypatch.setattr(workflow_types, "get_all_workflow_types", listing)

    response = _client(signed_in=False).get("/api/workflow-types")

    assert response.status_code == 200
    listing.assert_called_once_with()


def test_the_recent_selection_is_the_callers_and_needs_a_sign_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = AsyncMock(
        return_value=RecentWorkflowSelectionResponse(workflow_types=[])
    )
    monkeypatch.setattr(workflow_types, "get_recent_workflow_selection", selection)

    anonymous = _client(signed_in=False).get("/api/workflow-types/recent-selection")
    signed_in = _client().get("/api/workflow-types/recent-selection")

    assert (anonymous.status_code, signed_in.status_code) == (401, 200)
    selection.assert_awaited_once()
    assert selection.await_args_list[-1].args[0].id == CALLER


def test_estimates_need_a_project_id(estimates: AsyncMock) -> None:
    response = _client().get("/api/workflow-types/duration-estimates")

    assert response.status_code == 422
    estimates.assert_not_awaited()
