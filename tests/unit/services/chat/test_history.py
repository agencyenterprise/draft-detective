"""The checkpointed conversation: how a turn is built, read back, and shown."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from lib.services.chat import history
from lib.services.chat.history import (
    ChatAttachment,
    attachment_path,
    build_user_turn,
    delete_thread_state,
    load_thread_messages,
    read_thread_file,
    thread_config,
    to_ui_messages,
)


class TestBuildingATurn:
    def test_attachment_paths_are_safe_and_markdown(self) -> None:
        assert attachment_path("My Draft (v2).docx") == "/attachments/My-Draft-v2.md"
        assert attachment_path("report.pdf") == "/attachments/report.md"
        assert attachment_path("???.pdf") == "/attachments/document.md"

    def test_attachments_are_mounted_and_pointed_at(self) -> None:
        message, files = build_user_turn(
            "  Check the methods section.  ",
            [ChatAttachment(name="draft.docx", text="# Methods\n\nWe did things.")],
        )

        assert files == {"/attachments/draft.md": files["/attachments/draft.md"]}
        assert files["/attachments/draft.md"]["content"] == ["# Methods", "", "We did things."]

        assert message.text.startswith("Check the methods section.")
        assert 'Attached document "draft.docx" is mounted at /attachments/draft.md' in message.text
        assert message.additional_kwargs == {
            "user_text": "Check the methods section.",
            "attachments": [{"name": "draft.docx", "path": "/attachments/draft.md", "chars": 25}],
        }

    def test_the_page_picks_the_message_id(self) -> None:
        message, _ = build_user_turn("hi", [], message_id="page-id-1")
        assert message.id == "page-id-1"
        generated, _ = build_user_turn("hi", [])
        assert generated.id

    def test_a_turn_can_be_only_an_attachment(self) -> None:
        message, files = build_user_turn("", [ChatAttachment(name="a.pdf", text="body")])
        assert message.text.startswith('[Attached document "a.pdf"')
        assert message.additional_kwargs["user_text"] == ""
        assert set(files) == {"/attachments/a.md"}

    def test_the_thread_config_keys_the_checkpointer(self) -> None:
        assert thread_config("t-1") == {"configurable": {"thread_id": "t-1"}}


class TestUiMessages:
    def test_human_messages_show_what_the_user_typed(self) -> None:
        message = HumanMessage(
            content="hi\n\n[Attached document ...]",
            id="h1",
            additional_kwargs={"user_text": "hi", "attachments": [{"name": "a.pdf", "path": "/attachments/a.md", "chars": 4}]},
        )
        assert to_ui_messages([message]) == [
            {
                "id": "h1",
                "type": "human",
                "content": "hi",
                "additional_kwargs": {"attachments": [{"name": "a.pdf", "path": "/attachments/a.md", "chars": 4}]},
            }
        ]

    def test_a_plain_human_message_falls_back_to_its_text(self) -> None:
        assert to_ui_messages([HumanMessage(content="plain", id="h2")])[0]["content"] == "plain"

    def test_ai_content_is_rewritten_for_the_converter(self) -> None:
        """v1 reasoning becomes a summary list, adjacent text merges, hosted web
        search becomes a tool call with a result the converter can pair up."""
        message = AIMessage(
            id="a1",
            content=[
                {"type": "reasoning", "reasoning": "Weighing the claim.", "id": "rs_1"},
                {"type": "text", "text": "Hel"},
                {"type": "text", "text": "lo."},
                {"type": "server_tool_call", "id": "ws_1", "name": "web_search", "args": {"query": "q"}},
                {"type": "server_tool_result", "tool_call_id": "ws_1", "status": "completed"},
                {"type": "tool_call", "id": "c1", "name": "read_file", "args": {}},
            ],
            tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "/a"}}],
        )

        ai, result = to_ui_messages([message])
        assert ai == {
            "id": "a1",
            "type": "ai",
            "content": [
                {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Weighing the claim."}]},
                {"type": "text", "text": "Hello."},
            ],
            "tool_calls": [
                {"id": "c1", "name": "read_file", "args": {"file_path": "/a"}},
                {"id": "ws_1", "name": "web_search", "args": {"query": "q"}},
            ],
        }
        assert result["type"] == "tool" and result["tool_call_id"] == "ws_1"
        assert result["name"] == "web_search" and result["status"] == "success"

    def test_summary_layout_reasoning_is_accepted_too(self) -> None:
        message = AIMessage(
            id="a2",
            content=[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "A"}, {"type": "summary_text", "text": "B"}]}, {"type": "text", "text": "x"}],
        )
        assert to_ui_messages([message])[0]["content"][0]["summary"][0]["text"] == "AB"

    def test_empty_ai_messages_and_system_messages_are_dropped(self) -> None:
        messages = [SystemMessage(content="persona"), AIMessage(content="", id="a3"), HumanMessage(content="hi", id="h1")]
        assert [m["type"] for m in to_ui_messages(messages)] == ["human"]

    def test_tool_messages_keep_their_status(self) -> None:
        ok = ToolMessage(content="contents", tool_call_id="c1", name="read_file", id="t1")
        failed = ToolMessage(content="boom", tool_call_id="c2", name="grep", id="t2", status="error")
        assert to_ui_messages([ok, failed]) == [
            {"id": "t1", "type": "tool", "tool_call_id": "c1", "name": "read_file", "content": "contents", "status": "success"},
            {"id": "t2", "type": "tool", "tool_call_id": "c2", "name": "grep", "content": "boom", "status": "error"},
        ]


class FakeSaver:
    def __init__(self, values: dict[str, Any] | None) -> None:
        self.values = values
        self.deleted: list[str] = []

    async def aget_tuple(self, config: Any) -> Any:
        self.last_config = config
        if self.values is None:
            return None
        return SimpleNamespace(checkpoint={"channel_values": self.values})

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)


def _with_saver(saver: FakeSaver):
    @asynccontextmanager
    async def get_checkpointer():
        yield saver

    return patch.object(history, "get_checkpointer", get_checkpointer)


class TestReadingState:
    @pytest.mark.asyncio
    async def test_messages_come_from_the_latest_checkpoint(self) -> None:
        saver = FakeSaver({"messages": [HumanMessage(content="hi"), "not a message"], "files": {}})
        with _with_saver(saver):
            messages = await load_thread_messages("t-1")
        assert [m.content for m in messages] == ["hi"]
        assert saver.last_config == {"configurable": {"thread_id": "t-1"}}

    @pytest.mark.asyncio
    async def test_a_thread_never_run_has_no_messages(self) -> None:
        with _with_saver(FakeSaver(None)):
            assert await load_thread_messages("t-new") == []

    @pytest.mark.asyncio
    async def test_files_are_joined_back_into_text(self) -> None:
        saver = FakeSaver({"files": {"/attachments/a.md": {"content": ["one", "two"]}}})
        with _with_saver(saver):
            assert await read_thread_file("t-1", "/attachments/a.md") == "one\ntwo"
            assert await read_thread_file("t-1", "/attachments/missing.md") is None

    @pytest.mark.asyncio
    async def test_deleting_a_thread_deletes_its_checkpoints(self) -> None:
        saver = FakeSaver({})
        with _with_saver(saver):
            await delete_thread_state("t-1")
        assert saver.deleted == ["t-1"]


@pytest.mark.asyncio
async def test_the_saver_is_only_borrowed() -> None:
    """Every call opens its own context, matching how the pool is meant to be used."""
    entered = AsyncMock()

    @asynccontextmanager
    async def get_checkpointer():
        await entered()
        yield FakeSaver(None)

    with patch.object(history, "get_checkpointer", get_checkpointer):
        await load_thread_messages("a")
        await read_thread_file("a", "/x")
    assert entered.await_count == 2
