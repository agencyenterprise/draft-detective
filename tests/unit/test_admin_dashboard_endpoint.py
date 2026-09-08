"""The dashboard endpoints' guard, and how the ignore list crosses the wire.

Everything this page shows — who the users are, what they run, what they said
about the results — is admin-only. That property lives in a single `Depends`,
and nothing else in the suite would notice if it were dropped, so it is pinned
here rather than left to a manual check. The `exclude_user_ids` parameter is
pinned alongside: it is what makes the figures leave the eval account out, and
its normalisation is what keeps the cache from filling with one selection
spelled several ways.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import admin_dashboard
from lib.models.user import User, UserRole
from lib.services.admin_dashboard.models import (
    ActivityGranularity,
    AdminDashboardResponse,
    DashboardFeedbackSummary,
    DashboardIgnoredUser,
    MetricWithDelta,
)

EVAL_USER = DashboardIgnoredUser(
    user_id=uuid.uuid4(), name="E2E Eval Runner", email="eval@draft-detective.local"
)


def _user(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value.lower()}@example.com",
        name=f"{role.value} user",
        role=role,
        show_experimental_features=False,
    )


def _client(as_role: UserRole | None) -> TestClient:
    """Just this router, so the test does not depend on the whole app booting.

    `as_role=None` leaves authentication unstubbed, which is how an anonymous
    request reaches the endpoint.
    """
    app = FastAPI()
    app.include_router(admin_dashboard.router)
    if as_role is not None:
        app.dependency_overrides[get_current_user] = lambda: _user(as_role)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def stub_the_aggregates(monkeypatch):
    """No database: what is under test is who gets past the door, with what."""
    admin_dashboard._cached_dashboard.cache_clear()

    async def fake_dashboard(
        days: int, ignored_user_ids: tuple[uuid.UUID, ...]
    ) -> AdminDashboardResponse:
        now = datetime.now(timezone.utc)
        empty = MetricWithDelta(current=0, previous=0)
        return AdminDashboardResponse(
            period_days=days,
            period_start=now - timedelta(days=days),
            period_end=now,
            granularity=ActivityGranularity.DAY,
            cache_ttl_seconds=admin_dashboard.CACHE_TTL_SECONDS,
            ignored_user_ids=list(ignored_user_ids),
            total_users=0,
            active_users=empty,
            new_users=empty,
            projects_created=empty,
            assessments_run=empty,
            feedback_received=empty,
            activity=[],
            workflows=[],
            top_users=[],
            feedback=DashboardFeedbackSummary(
                thumbs_up=0, thumbs_down=0, with_comment=0
            ),
        )

    async def fake_default_ignored_users() -> list[DashboardIgnoredUser]:
        return [EVAL_USER]

    monkeypatch.setattr(admin_dashboard, "get_admin_dashboard", fake_dashboard)
    monkeypatch.setattr(
        admin_dashboard, "get_default_ignored_users", fake_default_ignored_users
    )
    yield
    admin_dashboard._cached_dashboard.cache_clear()


def test_an_ordinary_user_is_refused():
    response = _client(UserRole.USER).get("/api/admin/dashboard")

    assert response.status_code == 403


def test_a_rand_user_is_refused():
    """RAND is a workflow-access role, not an administrative one."""
    response = _client(UserRole.RAND).get("/api/admin/dashboard")

    assert response.status_code == 403


def test_an_anonymous_request_is_refused():
    response = _client(None).get("/api/admin/dashboard")

    assert response.status_code == 401


def test_an_admin_gets_the_payload():
    response = _client(UserRole.ADMIN).get("/api/admin/dashboard?days=7")

    assert response.status_code == 200
    assert response.json()["period_days"] == 7


@pytest.mark.parametrize("days", [0, -1, 731])
def test_the_window_length_is_bounded(days):
    """A window nobody asked for is a scan nobody needs."""
    response = _client(UserRole.ADMIN).get(f"/api/admin/dashboard?days={days}")

    assert response.status_code == 422


def test_nobody_is_excluded_unless_named():
    """The default ignore list is the UI's to apply, not the endpoint's."""
    response = _client(UserRole.ADMIN).get("/api/admin/dashboard")

    assert response.status_code == 200
    assert response.json()["ignored_user_ids"] == []


def test_excluded_users_reach_the_aggregates_sorted_and_deduplicated():
    """One selection, however spelled, is one cache entry and one payload."""
    low, high = sorted([uuid.uuid4(), uuid.uuid4()])
    query = f"exclude_user_ids={high}&exclude_user_ids={low}&exclude_user_ids={high}"

    response = _client(UserRole.ADMIN).get(f"/api/admin/dashboard?{query}")

    assert response.status_code == 200
    assert response.json()["ignored_user_ids"] == [str(low), str(high)]


def test_an_excluded_user_id_has_to_be_a_uuid():
    response = _client(UserRole.ADMIN).get(
        "/api/admin/dashboard?exclude_user_ids=eval@draft-detective.local"
    )

    assert response.status_code == 422


def test_the_ignore_list_is_bounded():
    """Past a few dozen users this is not a filter; refuse rather than scan."""
    too_many = "&".join(
        f"exclude_user_ids={uuid.uuid4()}"
        for _ in range(admin_dashboard._MAX_EXCLUDED_USERS + 1)
    )

    response = _client(UserRole.ADMIN).get(f"/api/admin/dashboard?{too_many}")

    assert response.status_code == 422


def test_the_default_ignore_list_is_admin_only():
    """It names a user by email, which is exactly what non-admins may not see."""
    assert (
        _client(UserRole.USER).get("/api/admin/dashboard/default-ignored-users")
    ).status_code == 403
    assert (
        _client(None).get("/api/admin/dashboard/default-ignored-users")
    ).status_code == 401


def test_an_admin_gets_the_default_ignore_list():
    response = _client(UserRole.ADMIN).get("/api/admin/dashboard/default-ignored-users")

    assert response.status_code == 200
    assert response.json() == [
        {
            "user_id": str(EVAL_USER.user_id),
            "name": EVAL_USER.name,
            "email": EVAL_USER.email,
        }
    ]
