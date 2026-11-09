"""The users endpoints' guards, and what they let out about the OpenAI key.

Listing users and changing anyone's role are admin-only, and each lives in one
`Depends`; the `/me` endpoints act on the caller and nobody else. A user's key
is validated before it is stored, and no response ever carries it: only
whether there is one. The services behind these routes have their own
integration tests, so here they are stubbed and only the routing is under test.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import users
from lib.models.user import User, UserRole
from lib.services.preflight.models import PreflightResult, ValidationIssue

CALLER = uuid.uuid4()
KEY = "sk-test-not-a-real-key"


def _user(role: UserRole = UserRole.USER, key: str | None = None) -> User:
    return User(
        id=CALLER,
        email="ana@example.com",
        name="Ana",
        role=role,
        show_experimental_features=False,
        encrypted_openai_api_key=key,
    )


def _client(as_role: UserRole | None = UserRole.USER) -> TestClient:
    """Just this router. `as_role=None` leaves authentication unstubbed: an anonymous request."""
    app = FastAPI()
    app.include_router(users.router)
    if as_role is not None:
        app.dependency_overrides[get_current_user] = lambda: _user(as_role)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    """The service calls the routes make, each answering with a plain user."""

    stubs = {
        "get_all_users": AsyncMock(return_value=[_user()]),
        "update_user_role": AsyncMock(return_value=_user(UserRole.ADMIN)),
        "update_user_preferences": AsyncMock(return_value=_user()),
        "set_user_openai_api_key": AsyncMock(return_value=_user(key="encrypted")),
        "delete_user_openai_api_key": AsyncMock(return_value=_user()),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(users, name, stub)
    return stubs


@pytest.fixture
def preflight(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    validate = AsyncMock(return_value=PreflightResult(valid=True))
    monkeypatch.setattr(users.PreflightValidationService, "validate", validate)
    return validate


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.RAND])
def test_only_an_admin_can_list_users_or_change_a_role(
    services: dict[str, AsyncMock], role: UserRole
) -> None:
    client = _client(role)

    listed = client.get("/api/users")
    changed = client.patch(f"/api/users/{uuid.uuid4()}/role", json={"role": "ADMIN"})

    assert (listed.status_code, changed.status_code) == (403, 403)
    services["get_all_users"].assert_not_awaited()
    services["update_user_role"].assert_not_awaited()


def test_an_anonymous_request_is_refused(services: dict[str, AsyncMock]) -> None:
    client = _client(as_role=None)

    assert client.get("/api/users/me").status_code == 401
    assert (
        client.patch(f"/api/users/{CALLER}/role", json={"role": "ADMIN"}).status_code
        == 401
    )
    services["update_user_role"].assert_not_awaited()


def test_an_admin_changes_the_named_users_role(services: dict[str, AsyncMock]) -> None:
    target = str(uuid.uuid4())

    response = _client(UserRole.ADMIN).patch(
        f"/api/users/{target}/role", json={"role": "RAND"}
    )

    assert response.status_code == 200
    services["update_user_role"].assert_awaited_once_with(target, UserRole.RAND)


def test_preferences_are_saved_on_the_caller(services: dict[str, AsyncMock]) -> None:
    response = _client().patch(
        "/api/users/me/preferences", json={"show_experimental_features": True}
    )

    assert response.status_code == 200
    services["update_user_preferences"].assert_awaited_once_with(str(CALLER), True)


def test_a_key_that_fails_validation_is_refused_and_not_stored(
    services: dict[str, AsyncMock], preflight: AsyncMock
) -> None:
    preflight.return_value = PreflightResult(
        valid=False,
        issues=[
            ValidationIssue(code="invalid_key", message="The key was rejected"),
            ValidationIssue(code="no_access", message="It cannot reach the model"),
        ],
    )

    response = _client().put("/api/users/me/api-key", json={"openai_api_key": KEY})

    assert response.status_code == 422
    assert (
        response.json()["detail"] == "The key was rejected; It cannot reach the model"
    )
    assert preflight.await_args is not None
    assert preflight.await_args.args[0].openai_api_key == KEY
    services["set_user_openai_api_key"].assert_not_awaited()


def test_a_valid_key_is_stored_for_the_caller_and_never_sent_back(
    services: dict[str, AsyncMock], preflight: AsyncMock
) -> None:
    response = _client().put("/api/users/me/api-key", json={"openai_api_key": KEY})

    assert response.status_code == 200
    services["set_user_openai_api_key"].assert_awaited_once_with(str(CALLER), KEY)
    assert response.json()["has_openai_api_key"] is True
    assert KEY not in response.text and "encrypted" not in response.text


def test_the_caller_is_told_whether_a_key_is_stored_but_not_what_it_is() -> None:
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[get_current_user] = lambda: _user(key="encrypted-value")

    response = TestClient(app).get("/api/users/me")

    assert response.json()["has_openai_api_key"] is True
    assert "encrypted-value" not in response.text


def test_removing_the_key_removes_the_callers(services: dict[str, AsyncMock]) -> None:
    response = _client().delete("/api/users/me/api-key")

    assert response.status_code == 200
    services["delete_user_openai_api_key"].assert_awaited_once_with(str(CALLER))
    assert response.json()["has_openai_api_key"] is False
