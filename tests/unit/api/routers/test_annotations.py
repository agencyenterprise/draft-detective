"""The annotation endpoints' guards and what they pass to the services.

Annotating is for any signed-in user and acts as the caller; reading the
results is admin-only, through one `Depends`. A submission's outcome never
carries the reference answers, so an annotator can't learn how the dataset
answered. The services have their own integration tests, so here they are
stubbed and only the routing is under test.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import annotations
from lib.models.user import User, UserRole
from lib.services.annotations.models import (
    AnnotationOutcome,
    AnnotationTask,
    AnnotationTaskSet,
)

CALLER = uuid.uuid4()
ITEM = uuid.uuid4()
ADMIN_PATHS = [
    "/api/admin/annotations/sets",
    "/api/admin/annotations/export",
    "/api/admin/annotations/sets/abbreviations/items",
]


def _user(role: UserRole) -> User:
    return User(
        id=CALLER,
        email="ana@example.com",
        name="Ana",
        role=role,
        show_experimental_features=False,
    )


def _client(as_role: UserRole | None = UserRole.USER) -> TestClient:
    """Just this router. `as_role=None` leaves authentication unstubbed: an anonymous request."""
    app = FastAPI()
    app.include_router(annotations.router)
    if as_role is not None:
        app.dependency_overrides[get_current_user] = lambda: _user(as_role)
    return TestClient(app, raise_server_exceptions=False)


def _task() -> AnnotationTask:
    return AnnotationTask(
        set=AnnotationTaskSet(
            slug="abbreviations", title="Abbreviations", guidance="", questions=[]
        ),
        item_id=ITEM,
        item_count=3,
        answered_by_me=1,
    )


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    stubs = {
        "list_sets": AsyncMock(return_value=[]),
        "next_task": AsyncMock(return_value=_task()),
        "submit_annotation": AsyncMock(
            return_value=AnnotationOutcome(item_id=ITEM, answered_by_me=2)
        ),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(annotations.annotation_service, name, stub)
    return stubs


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    stubs = {
        "list_set_stats": AsyncMock(return_value=[]),
        "export_annotations": AsyncMock(return_value=[]),
        "list_annotated_items": AsyncMock(return_value=[]),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(annotations.annotation_admin, name, stub)
    return stubs


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.RAND])
def test_only_an_admin_reads_the_results(
    admin: dict[str, AsyncMock], role: UserRole
) -> None:
    client = _client(role)

    statuses = [client.get(path).status_code for path in ADMIN_PATHS]

    assert statuses == [403, 403, 403]
    for stub in admin.values():
        stub.assert_not_awaited()


def test_an_anonymous_request_is_refused(
    service: dict[str, AsyncMock], admin: dict[str, AsyncMock]
) -> None:
    client = _client(as_role=None)

    statuses = [
        client.get("/api/annotations/sets").status_code,
        client.get("/api/annotations/sets/abbreviations/next").status_code,
        client.put(f"/api/annotations/items/{ITEM}", json={"answers": {}}).status_code,
        *(client.get(path).status_code for path in ADMIN_PATHS),
    ]

    assert set(statuses) == {401}
    for stub in [*service.values(), *admin.values()]:
        stub.assert_not_awaited()


def test_an_admin_reads_a_sets_items_with_the_disagreement_filter(
    admin: dict[str, AsyncMock],
) -> None:
    client = _client(UserRole.ADMIN)

    everything = client.get("/api/admin/annotations/sets/abbreviations/items")
    contested = client.get(
        "/api/admin/annotations/sets/abbreviations/items",
        params={"only_disagreements": "true"},
    )

    assert (everything.status_code, contested.status_code) == (200, 200)
    assert [c.args for c in admin["list_annotated_items"].await_args_list] == [
        ("abbreviations", False),
        ("abbreviations", True),
    ]


def test_the_next_task_is_picked_for_the_caller_past_the_skipped_items(
    service: dict[str, AsyncMock],
) -> None:
    skipped = [uuid.uuid4(), uuid.uuid4()]

    response = _client().get(
        "/api/annotations/sets/abbreviations/next",
        params={"skip": [str(item) for item in skipped]},
    )

    assert response.status_code == 200
    assert response.json()["item_id"] == str(ITEM)
    slug, user, skip = service["next_task"].await_args_list[-1].args
    assert (slug, user.id, skip) == ("abbreviations", CALLER, skipped)


@pytest.mark.parametrize(
    "skip",
    [["not-a-uuid"], [str(uuid.uuid4()) for _ in range(101)]],
    ids=["malformed", "over-the-cap"],
)
def test_a_bad_skip_list_is_refused_before_the_query(
    service: dict[str, AsyncMock], skip: list[str]
) -> None:
    response = _client().get(
        "/api/annotations/sets/abbreviations/next", params={"skip": skip}
    )

    assert response.status_code == 422
    service["next_task"].assert_not_awaited()


def test_a_submission_is_saved_as_the_caller_and_hides_the_reference(
    service: dict[str, AsyncMock],
) -> None:
    response = _client().put(
        f"/api/annotations/items/{ITEM}",
        json={"answers": {"q": "no"}, "comment": "unsure", "time_spent_ms": 900},
    )

    assert response.status_code == 200
    assert response.json() == {"item_id": str(ITEM), "answered_by_me": 2}
    item_id, user, submission = service["submit_annotation"].await_args_list[-1].args
    assert (item_id, user.id) == (ITEM, CALLER)
    assert submission.answers == {"q": "no"}
    assert submission.time_spent_ms == 900


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/annotations/items/not-a-uuid", {"answers": {}}),
        (f"/api/annotations/items/{ITEM}", {"answers": {}, "time_spent_ms": -1}),
        (f"/api/annotations/items/{ITEM}", {"answers": {}, "comment": "x" * 4001}),
        (f"/api/annotations/items/{ITEM}", {}),
    ],
    ids=["bad-item-id", "negative-time", "long-comment", "no-answers"],
)
def test_a_malformed_submission_is_refused_before_saving(
    service: dict[str, AsyncMock], path: str, body: dict[str, object]
) -> None:
    response = _client().put(path, json=body)

    assert response.status_code == 422
    service["submit_annotation"].assert_not_awaited()
