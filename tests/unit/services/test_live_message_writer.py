"""Unit tests for LiveMessageWriter — redaction and aupdate_state wiring."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from lib.services.live_message_writer import (
    _MAX_TOOL_CONTENT_CHARS,
    _REDACTED_PLACEHOLDER,
    _TRUNCATION_MARKER,
    LiveMessageWriter,
)


def _make_writer() -> tuple[LiveMessageWriter, AsyncMock]:
    app = Mock()
    app.aupdate_state = AsyncMock()
    writer = LiveMessageWriter(
        app=app,
        thread_config={"configurable": {"thread_id": "thread-123"}},
        node_name="run_agent",
    )
    return writer, app.aupdate_state


class TestRedaction:
    @pytest.mark.asyncio
    async def test_openai_api_key_is_scrubbed_from_content(self):
        """Any substring matching the sk-... pattern gets replaced with the placeholder."""
        writer, update = _make_writer()
        leaked = (
            "Here is my key: sk-proj-ABCDEFG1234567890_abcdefghij please keep it safe"
        )

        await writer.append(AIMessage(content=leaked))

        assert update.await_count == 1
        persisted = update.await_args.args[1]["messages"][0]
        assert "sk-proj-" not in persisted.content
        assert _REDACTED_PLACEHOLDER in persisted.content
        assert "please keep it safe" in persisted.content

    @pytest.mark.asyncio
    async def test_redaction_walks_structured_content_blocks(self):
        """List-shaped content (LangChain content blocks) is redacted recursively."""
        writer, update = _make_writer()
        blocks = [
            {"type": "text", "text": "leaking sk-abcdefghij1234567890klmnop now"},
            {"type": "text", "text": "harmless"},
        ]

        await writer.append(AIMessage(content=blocks))

        persisted = update.await_args.args[1]["messages"][0]
        assert _REDACTED_PLACEHOLDER in persisted.content[0]["text"]
        assert persisted.content[1]["text"] == "harmless"

    @pytest.mark.asyncio
    async def test_short_strings_without_api_keys_are_passed_through(self):
        """No accidental mangling of plain content."""
        writer, update = _make_writer()

        await writer.append(AIMessage(content="plain response with no secrets"))

        persisted = update.await_args.args[1]["messages"][0]
        assert persisted.content == "plain response with no secrets"


class TestToolTruncation:
    @pytest.mark.asyncio
    async def test_large_tool_content_is_truncated(self):
        """ToolMessage content exceeding the cap is truncated with a marker."""
        writer, update = _make_writer()
        huge = "x" * (_MAX_TOOL_CONTENT_CHARS + 5_000)

        await writer.append(ToolMessage(content=huge, tool_call_id="t1"))

        persisted = update.await_args.args[1]["messages"][0]
        assert len(persisted.content) == _MAX_TOOL_CONTENT_CHARS + len(_TRUNCATION_MARKER)
        assert persisted.content.endswith(_TRUNCATION_MARKER)

    @pytest.mark.asyncio
    async def test_small_tool_content_is_not_touched(self):
        writer, update = _make_writer()

        await writer.append(ToolMessage(content="tiny result", tool_call_id="t1"))

        persisted = update.await_args.args[1]["messages"][0]
        assert persisted.content == "tiny result"

    @pytest.mark.asyncio
    async def test_truncation_only_applies_to_tool_messages(self):
        """AIMessage and HumanMessage are not capped — they're generally small,
        and the LLM's own output shouldn't be silently chopped."""
        writer, update = _make_writer()
        huge = "y" * (_MAX_TOOL_CONTENT_CHARS + 1_000)

        await writer.append(AIMessage(content=huge))

        persisted = update.await_args.args[1]["messages"][0]
        assert persisted.content == huge


class TestAupdateStateWiring:
    @pytest.mark.asyncio
    async def test_passes_correct_thread_config_and_node_name(self):
        writer, update = _make_writer()

        await writer.append(AIMessage(content="hello"))

        assert update.await_count == 1
        args, kwargs = update.await_args
        assert args[0] == {"configurable": {"thread_id": "thread-123"}}
        assert args[1]["messages"][0].content == "hello"
        assert kwargs["as_node"] == "run_agent"

    @pytest.mark.asyncio
    async def test_append_does_not_mutate_caller_message(self):
        """The original BaseMessage passed in by the caller must stay intact —
        redaction operates on a copy so the agent's own references are safe."""
        writer, _ = _make_writer()
        original = AIMessage(content="key: sk-abcdefghij1234567890klmnop")

        await writer.append(original)

        assert "sk-" in original.content  # caller's copy still has the secret
        assert _REDACTED_PLACEHOLDER not in original.content

    @pytest.mark.asyncio
    async def test_checkpoint_failure_does_not_raise(self):
        """aupdate_state errors are logged, not re-raised — we never want a
        streaming-persistence hiccup to abort the workflow."""
        writer, update = _make_writer()
        update.side_effect = RuntimeError("checkpoint table busy")

        # Should not raise
        await writer.append(HumanMessage(content="ok"))

        assert update.await_count == 1
