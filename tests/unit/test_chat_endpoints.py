"""The agent-facing chat endpoints, with the model and database stubbed out.

What is pinned: who gets past the door, what the picker and slash-command menu
are fed, that a turn streams as server-sent events built from the graph's
output, that a title lands on the thread, and how attachment extraction fails.
"""

import io
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from lib.agents import chat_agent as chat_agent_module
from lib.api.auth import get_current_user
from lib.api.routers import chat
from lib.models.chat_thread import ChatThread
from lib.models.user import User, UserRole
from lib.workflows.registry import get_all_manifests

USER = User(
    id=uuid.uuid4(),
    email="reviewer@example.com",
    name="Reviewer",
    role=UserRole.USER,
    show_experimental_features=False,
)
THREAD_ID = uuid.uuid4()


def _thread(title: str | None = None) -> ChatThread:
    now = datetime.now(timezone.utc)
    return ChatThread(
        id=THREAD_ID, user_id=USER.id, title=title, created_at=now, last_updated_at=now
    )


def _client(authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(chat.router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


class FakeGraph:
    """Stands in for the compiled deep agent: replays a scripted stream."""

    def __init__(self, script: list[tuple[str, Any]]) -> None:
        self.script = script
        self.calls: list[dict[str, Any]] = []

    async def astream(self, agent_input: Any, config: Any, stream_mode: Any) -> AsyncIterator[Any]:
        self.calls.append({"input": agent_input, "config": config, "stream_mode": stream_mode})
        for item in self.script:
            yield item


def _frames(body: str) -> list[str]:
    return [frame for frame in body.split("\n\n") if frame]


class TestGuard:
    def test_anonymous_requests_are_refused(self) -> None:
        client = _client(authenticated=False)
        assert client.get("/api/chat/models").status_code == 401
        assert client.get("/api/chat/skills").status_code == 401
        assert (
            client.post(f"/api/chat/threads/{THREAD_ID}/stream", json={"messages": []}).status_code
            == 401
        )


class TestCatalogues:
    def test_models_come_from_the_allowlist_with_one_default(self) -> None:
        rows = _client().get("/api/chat/models").json()
        assert [row["id"] for row in rows] == [o.id for o in chat_agent_module.CHAT_MODELS]
        assert [row["is_default"] for row in rows].count(True) == 1
        assert rows[0]["id"] == chat_agent_module.DEFAULT_CHAT_MODEL.name

    def test_skills_leave_out_the_excluded_ones(self) -> None:
        names = {row["name"] for row in _client().get("/api/chat/skills").json()}
        assert "reference-validation" in names
        assert "voice-and-tone" in names
        assert names.isdisjoint(chat_agent_module.EXCLUDED_CHAT_SKILLS)

    def test_skill_descriptions_come_from_the_workflow_manifest_when_there_is_one(self) -> None:
        rows = {row["name"]: row["description"] for row in _client().get("/api/chat/skills").json()}
        manifests = get_all_manifests()
        for skill_name, workflow_type in chat_agent_module.SKILL_WORKFLOWS.items():
            assert skill_name in rows, f"{skill_name} is mapped but not on disk"
            assert rows[skill_name] == manifests[workflow_type].description
        # A helper skill keeps its own SKILL.md description.
        assert rows["voice-and-tone"].startswith("How Draft Detective writes.")


class TestStream:
    @pytest.fixture
    def graph(self) -> FakeGraph:
        return FakeGraph(
            [
                ("messages", (AIMessageChunk(content=[{"type": "reasoning", "reasoning": "hm"}]), {})),
                (
                    "updates",
                    {
                        "model": {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "/skills/x"}}],
                                )
                            ]
                        }
                    },
                ),
                ("updates", {"tools": {"messages": [ToolMessage(content="skill text", tool_call_id="c1")]}}),
                ("messages", (AIMessageChunk(content=[{"type": "text", "text": "Done."}]), {})),
            ]
        )

    def test_a_turn_streams_the_graph_as_events(self, graph: FakeGraph) -> None:
        with (
            patch.object(chat.chat_thread_service, "get_thread", AsyncMock(return_value=_thread())),
            patch.object(chat, "build_chat_agent", return_value=graph) as build,
        ):
            response = _client().post(
                f"/api/chat/threads/{THREAD_ID}/stream",
                json={
                    "model": "gpt-5.6-luna",
                    "messages": [
                        {"role": "user", "content": "hi"},
                        {"role": "assistant", "content": "hello"},
                        {"role": "user", "content": "Attached document \"a.pdf\":\n\nbody"},
                    ],
                },
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert [frame.split("\n")[0][:30] for frame in _frames(response.text)] == [
            'data: {"t": "reasoning", "v": ',
            'data: {"t": "tool", "id": "c1"',
            'data: {"t": "tool_result", "id',
            'data: {"t": "text", "v": "Done',
        ]

        build.assert_called_once()
        model, api_key = build.call_args.args
        assert model.name == "gpt-5.6-luna" and api_key is None

        run = graph.calls[0]
        assert [m.type for m in run["input"]["messages"]] == ["human", "ai", "human"]
        assert "/skills/voice-and-tone/SKILL.md" in run["input"]["files"]
        assert run["config"]["metadata"]["langfuse_session_id"] == str(THREAD_ID)
        assert run["stream_mode"] == ["messages", "updates"]

    def test_an_unknown_model_falls_back_to_the_default(self, graph: FakeGraph) -> None:
        with (
            patch.object(chat.chat_thread_service, "get_thread", AsyncMock(return_value=_thread())),
            patch.object(chat, "build_chat_agent", return_value=graph) as build,
        ):
            _client().post(
                f"/api/chat/threads/{THREAD_ID}/stream",
                json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hi"}]},
            )
        assert build.call_args.args[0] == chat_agent_module.DEFAULT_CHAT_MODEL

    def test_a_conversation_not_ending_with_the_user_is_rejected(self) -> None:
        with patch.object(chat.chat_thread_service, "get_thread", AsyncMock(return_value=_thread())):
            response = _client().post(
                f"/api/chat/threads/{THREAD_ID}/stream",
                json={"messages": [{"role": "assistant", "content": "hello"}]},
            )
        assert response.status_code == 422

    def test_a_graph_failure_ends_the_stream_with_an_error_event(self) -> None:
        class FailingGraph:
            async def astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
                yield ("messages", (AIMessageChunk(content="part"), {}))
                raise RuntimeError("rate limited")

        with (
            patch.object(chat.chat_thread_service, "get_thread", AsyncMock(return_value=_thread())),
            patch.object(chat, "build_chat_agent", return_value=FailingGraph()),
        ):
            response = _client().post(
                f"/api/chat/threads/{THREAD_ID}/stream",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        frames = _frames(response.text)
        assert response.status_code == 200
        assert frames[-1] == 'data: {"t": "error", "v": "rate limited"}'


class TestTitle:
    def test_the_generated_title_is_stored_on_the_thread(self) -> None:
        with (
            patch.object(chat.chat_thread_service, "get_thread", AsyncMock(return_value=_thread())),
            patch.object(chat, "generate_title", AsyncMock(return_value="Citation check")),
            patch.object(
                chat.chat_thread_service,
                "rename_thread",
                AsyncMock(return_value=_thread(title="Citation check")),
            ) as rename,
        ):
            response = _client().post(
                f"/api/chat/threads/{THREAD_ID}/title",
                json={"messages": [{"role": "user", "content": "check my citations"}]},
            )
        assert response.status_code == 200
        assert response.json()["title"] == "Citation check"
        assert rename.call_args.kwargs["title"] == "Citation check"


class TestExtract:
    def test_a_docx_comes_back_as_markdown(self) -> None:
        document = Document()
        document.add_heading("Findings", level=1)
        document.add_paragraph("The effect was small.")
        buffer = io.BytesIO()
        document.save(buffer)

        response = _client().post(
            "/api/chat/extract", files={"file": ("draft.docx", buffer.getvalue())}
        )
        assert response.status_code == 200
        assert "Findings" in response.json()["text"]
        assert "The effect was small." in response.json()["text"]

    def test_other_types_are_refused(self) -> None:
        response = _client().post("/api/chat/extract", files={"file": ("notes.txt", b"hello")})
        assert response.status_code == 415

    def test_an_empty_document_is_reported(self) -> None:
        buffer = io.BytesIO()
        Document().save(buffer)
        response = _client().post(
            "/api/chat/extract", files={"file": ("blank.docx", buffer.getvalue())}
        )
        assert response.status_code == 422
