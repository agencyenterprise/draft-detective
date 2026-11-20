"""The /live-reports files endpoint, with the database and checkpointer stubbed out."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.agents import live_report_agent
from lib.api.auth import get_current_user
from lib.api.routers import live_reports
from lib.models.chat_thread import ChatThread, ChatThreadKind
from lib.models.user import User, UserRole
from lib.services.chat.thread_state import ThreadFile

USER = User(
    id=uuid.uuid4(),
    email="reviewer@example.com",
    name="Reviewer",
    role=UserRole.USER,
    show_experimental_features=False,
)
THREAD_ID = uuid.uuid4()


def _thread(kind: ChatThreadKind) -> ChatThread:
    now = datetime.now(UTC)
    return ChatThread(
        id=THREAD_ID, user_id=USER.id, kind=kind, created_at=now, last_updated_at=now
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(live_reports.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


def test_the_files_are_listed_by_their_path_in_the_folder() -> None:
    at = "2026-11-20T10:00:00+00:00"
    files = {
        "/live-report/intake.md": ThreadFile(content="# Intake", modified_at=at),
        "/live-report/research-plan.md": ThreadFile(content="# Research plan"),
        "/live-report/research/F1.md": ThreadFile(content="# F1", modified_at=at),
    }
    with (
        patch.object(
            live_reports.chat_thread_service,
            "get_thread",
            AsyncMock(return_value=_thread(ChatThreadKind.LIVE_REPORT)),
        ),
        patch.object(
            live_reports, "list_thread_files", AsyncMock(return_value=files)
        ) as listed,
    ):
        response = _client().get(f"/api/live-reports/{THREAD_ID}/files")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "intake.md", "content": "# Intake", "modified_at": at},
        {"name": "research-plan.md", "content": "# Research plan", "modified_at": None},
        {"name": "research/F1.md", "content": "# F1", "modified_at": at},
    ]
    listed.assert_awaited_once_with(
        str(THREAD_ID),
        "/live-report",
        reader=live_report_agent.live_report_reader,
    )


def test_a_chat_thread_is_not_a_live_report() -> None:
    with (
        patch.object(
            live_reports.chat_thread_service,
            "get_thread",
            AsyncMock(return_value=_thread(ChatThreadKind.CHAT)),
        ),
        patch.object(live_reports, "list_thread_files", AsyncMock()) as listed,
    ):
        response = _client().get(f"/api/live-reports/{THREAD_ID}/files")

    assert response.status_code == 404
    listed.assert_not_awaited()
