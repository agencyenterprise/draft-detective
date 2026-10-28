"""POST /api/feedback validates feedback_type before it reaches the service."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers import feedback
from lib.models.feedback import Feedback, FeedbackType
from lib.models.user import User, UserRole

USER = User(
    id=uuid.uuid4(),
    email="reviewer@example.com",
    name="Reviewer",
    role=UserRole.USER,
    show_experimental_features=False,
)
RUN_ID = uuid.uuid4()


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncMock]:
    yield AsyncMock()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(feedback.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


def _stored(feedback_type: FeedbackType) -> Feedback:
    now = datetime.now(UTC)
    return Feedback(
        id=uuid.uuid4(),
        workflow_run_id=RUN_ID,
        user_id=USER.id,
        entity_path={"chunk_index": 0},
        feedback_type=feedback_type,
        created_at=now,
        updated_at=now,
    )


def test_an_unknown_feedback_type_is_a_422():
    service = AsyncMock()
    with patch.object(feedback.feedback_service, "create_or_update_feedback", service):
        response = _client().post(
            "/api/feedback",
            json={"workflow_run_id": str(RUN_ID), "feedback_type": "meh"},
        )

    assert response.status_code == 422
    service.assert_not_called()


def test_a_known_feedback_type_reaches_the_service_as_the_enum():
    service = AsyncMock(return_value=_stored(FeedbackType.THUMBS_DOWN))
    with (
        patch.object(feedback, "get_async_db_session", _session),
        patch.object(feedback.feedback_service, "create_or_update_feedback", service),
    ):
        response = _client().post(
            "/api/feedback",
            json={
                "workflow_run_id": str(RUN_ID),
                "entity_path": {"chunk_index": 0},
                "feedback_type": "thumbs_down",
            },
        )

    assert response.status_code == 200
    assert response.json()["feedback_type"] == "thumbs_down"
    assert service.call_args.kwargs["feedback_type"] is FeedbackType.THUMBS_DOWN
