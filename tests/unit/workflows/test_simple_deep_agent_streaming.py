"""Unit tests for SimpleDeepAgent's streaming branch.

Covers the two paths in `SimpleDeepAgent.ainvoke`:
- `live_message_writer is None` → blocking `deep_agent.ainvoke` (unchanged legacy behavior)
- `live_message_writer is set`  → iterate `deep_agent.astream` and call
  `writer.append` once per newly-produced message, returning the final
  accumulated state.
"""

from typing import AsyncIterator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from lib.services.file_artifacts_service.file_artifacts_service_type import (
    FileArtifactsServiceType,
)
from lib.services.live_message_writer import LiveMessageWriter
from lib.workflows.context import ContextSchema
from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent
from lib.workflows.simple_deep_agent.types import AgentCheckResult


def _make_context(writer=None) -> ContextSchema:
    # The agent only reads `file_artifacts_service.get_deepagent_backend_files`
    # during ainvoke and hands the result straight to the (mocked) deep_agent,
    # so a spec'd Mock with one async method is enough.
    fake_file_service = Mock(spec=FileArtifactsServiceType)
    fake_file_service.get_deepagent_backend_files = AsyncMock(return_value={})
    return ContextSchema(
        project_id="p1",
        file_artifacts_service=fake_file_service,
        live_message_writer=writer,
        openai_api_key="sk-test",
    )


def _make_writer_mock() -> Mock:
    writer = Mock(spec=LiveMessageWriter)
    writer.append = AsyncMock()
    return writer


def _make_agent(writer=None) -> SimpleDeepAgent:
    # LangChainAgent.__init__ may try to construct an LLM client. We only
    # exercise ainvoke's streaming logic, and ainvoke constructs its own
    # deep_agent (which we mock out), so the llm attribute is never actually
    # used during these tests.
    with patch.object(SimpleDeepAgent, "llm", Mock(), create=True):
        return SimpleDeepAgent(context=_make_context(writer=writer), user_prompt="check X")


class _StreamingAgent:
    """Stand-in for a compiled deep_agent whose astream yields `values`-mode
    state snapshots with a growing `messages` list."""

    def __init__(self, yields: list[dict]):
        self._yields = yields

    async def astream(self, inputs, config, stream_mode):
        assert stream_mode == "values"
        for chunk in self._yields:
            yield chunk

    async def ainvoke(self, inputs, config):
        # Final state = last yield
        return self._yields[-1]


class TestLegacyPath:
    @pytest.mark.asyncio
    async def test_no_writer_calls_ainvoke_and_returns_final(self):
        final_result = AgentCheckResult(issues=[], report_markdown="done")
        messages = [AIMessage(content="hello", id="a1")]

        agent = _make_agent(writer=None)
        stub = _StreamingAgent([{"structured_response": final_result, "messages": messages}])

        with patch(
            "lib.workflows.simple_deep_agent.agent.create_deep_agent",
            return_value=stub,
        ):
            result, out_messages = await agent.ainvoke({})

        assert result is final_result
        assert out_messages == messages


class TestStreamingPath:
    @pytest.mark.asyncio
    async def test_writer_called_once_per_new_message(self):
        """Streaming should call writer.append exactly once per new message,
        using the diff between successive state snapshots."""
        writer = _make_writer_mock()

        msg_a = AIMessage(content="thinking…", id="a")
        msg_b = ToolMessage(content="tool result", tool_call_id="t1", id="b")
        msg_c = AIMessage(content="final", id="c")
        final_result = AgentCheckResult(issues=[], report_markdown="done")

        stub = _StreamingAgent([
            # step 1: just the first LLM message
            {"structured_response": None, "messages": [msg_a]},
            # step 2: adds a tool result
            {"structured_response": None, "messages": [msg_a, msg_b]},
            # step 3: final LLM message + structured output
            {"structured_response": final_result, "messages": [msg_a, msg_b, msg_c]},
        ])

        agent = _make_agent(writer=writer)
        with patch(
            "lib.workflows.simple_deep_agent.agent.create_deep_agent",
            return_value=stub,
        ):
            result, messages = await agent.ainvoke({})

        assert result is final_result
        assert messages == [msg_a, msg_b, msg_c]
        # Exactly 3 appends, in order
        assert writer.append.await_count == 3
        appended = [call.args[0] for call in writer.append.await_args_list]
        assert appended == [msg_a, msg_b, msg_c]

    @pytest.mark.asyncio
    async def test_identical_snapshots_do_not_trigger_duplicate_appends(self):
        """If the deep agent yields the same state snapshot twice (no new
        messages), the writer must not be called again for the same messages."""
        writer = _make_writer_mock()

        msg = AIMessage(content="only", id="only")
        stub = _StreamingAgent([
            {"structured_response": None, "messages": [msg]},
            {"structured_response": None, "messages": [msg]},  # no new messages
            {"structured_response": AgentCheckResult(), "messages": [msg]},
        ])

        agent = _make_agent(writer=writer)
        with patch(
            "lib.workflows.simple_deep_agent.agent.create_deep_agent",
            return_value=stub,
        ):
            await agent.ainvoke({})

        assert writer.append.await_count == 1

    @pytest.mark.asyncio
    async def test_empty_stream_falls_back_to_ainvoke(self):
        """Defensive: if astream yields nothing at all, ainvoke is used so the
        workflow still gets a structured result."""
        writer = _make_writer_mock()

        fallback_result = AgentCheckResult(issues=[], report_markdown="from fallback")

        stub = Mock()
        stub.astream = Mock(return_value=_empty_async_iter())
        stub.ainvoke = AsyncMock(
            return_value={"structured_response": fallback_result, "messages": []}
        )

        agent = _make_agent(writer=writer)
        with patch(
            "lib.workflows.simple_deep_agent.agent.create_deep_agent",
            return_value=stub,
        ):
            result, messages = await agent.ainvoke({})

        assert result is fallback_result
        assert messages == []
        # No messages produced → writer must not have been called.
        assert writer.append.await_count == 0
        stub.ainvoke.assert_awaited_once()


async def _empty_async_iter() -> AsyncIterator[dict]:
    if False:  # pragma: no cover - generator that yields nothing
        yield {}
