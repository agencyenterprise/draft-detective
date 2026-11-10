"""The duration-estimates cache must not be bypassable by varying `project_id`.

The estimate is one aggregate over every completed run in `workflow_runs`, and
the service ignores `project_id`. If the cache were keyed on it, every caller
who sends a new id would trigger a fresh scan.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user_optional
from lib.api.routers import workflow_types
from lib.services.workflow_duration_estimates import WorkflowDurationEstimatesResponse


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    workflow_types._cached_duration_estimates.cache_clear()
    yield
    workflow_types._cached_duration_estimates.cache_clear()


@pytest.fixture
def service_calls(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    async def fake_service(*args: Any) -> WorkflowDurationEstimatesResponse:
        calls.append(args)
        return WorkflowDurationEstimatesResponse(estimates=[])

    monkeypatch.setattr(workflow_types, "get_workflow_duration_estimates", fake_service)
    return calls


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(workflow_types.router)
    app.dependency_overrides[get_current_user_optional] = lambda: None
    # One event loop for every request, as in the server: the cache is per loop.
    with TestClient(app) as test_client:
        yield test_client


def test_distinct_project_ids_share_one_computation(
    client: TestClient, service_calls: list[Any]
) -> None:
    for i in range(5):
        response = client.get(
            "/api/workflow-types/duration-estimates", params={"project_id": f"x{i}"}
        )
        assert response.status_code == 200
        assert response.json() == {"estimates": []}

    assert len(service_calls) == 1
