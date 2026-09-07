"""The graph stream, mapped to the five events the /chat page renders.

Chunk shapes here mirror what langchain-openai emits under ``output_version="v1"``
through a deep agent (captured in a spike before this was written): text and
reasoning content blocks in the token stream, ``tool_call_chunk`` blocks that
are deliberately ignored there, and completed messages in ``updates``.
"""

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Overwrite

from lib.services.chat.events import GraphEventMapper, content_blocks


def _tokens(*blocks: dict) -> tuple:
    return (AIMessageChunk(content=list(blocks)), {"langgraph_node": "model"})


class TestTokenStream:
    def test_text_and_reasoning_deltas_become_events(self) -> None:
        mapper = GraphEventMapper()
        events = mapper.map(
            "messages",
            _tokens(
                {"type": "reasoning", "reasoning": "Weighing ", "index": "lc_rs_1"},
                {"type": "text", "text": "Hello", "phase": "final_answer"},
            ),
        )
        assert events == [
            {"t": "reasoning", "v": "Weighing "},
            {"t": "text", "v": "Hello"},
        ]

    def test_empty_blocks_and_tool_call_chunks_are_skipped(self) -> None:
        """The first reasoning block carries no text, and arguments stream as
        chunks; neither is something the page can render on its own."""
        mapper = GraphEventMapper()
        events = mapper.map(
            "messages",
            _tokens(
                {"type": "reasoning", "id": "rs_1", "extras": {"content": []}},
                {"type": "text", "text": ""},
                {"type": "tool_call_chunk", "name": "read_file", "args": '{"pa'},
            ),
        )
        assert events == []

    def test_string_content_is_a_text_delta(self) -> None:
        mapper = GraphEventMapper()
        chunk: tuple[AIMessageChunk, dict] = (AIMessageChunk(content="plain"), {})
        assert mapper.map("messages", chunk) == [{"t": "text", "v": "plain"}]

    def test_tool_messages_in_the_token_stream_are_ignored(self) -> None:
        """They are handled from ``updates``; doing both would double them."""
        mapper = GraphEventMapper()
        payload: tuple[ToolMessage, dict] = (ToolMessage(content="result", tool_call_id="c1"), {})
        assert mapper.map("messages", payload) == []


class TestUpdates:
    def test_completed_tool_calls_are_announced_with_whole_args(self) -> None:
        mapper = GraphEventMapper()
        message = AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "/a"}}],
        )
        events = mapper.map("updates", {"model": {"messages": [message]}})
        assert events == [
            {"t": "tool", "id": "c1", "name": "read_file", "args": {"file_path": "/a"}}
        ]

    def test_a_tool_message_is_a_result(self) -> None:
        mapper = GraphEventMapper()
        ok = ToolMessage(content="contents", tool_call_id="c1")
        failed = ToolMessage(content="boom", tool_call_id="c2", status="error")
        events = mapper.map("updates", {"tools": {"messages": [ok, failed]}})
        assert events == [
            {"t": "tool_result", "id": "c1", "result": "contents"},
            {"t": "tool_result", "id": "c2", "result": "boom", "isError": True},
        ]

    def test_hosted_web_search_comes_from_content_blocks(self) -> None:
        mapper = GraphEventMapper()
        message = AIMessage(
            content=[
                {
                    "type": "server_tool_call",
                    "name": "web_search",
                    "id": "ws_1",
                    "args": {"query": "attention is all you need"},
                },
                {"type": "server_tool_result", "tool_call_id": "ws_1", "status": "success"},
                {"type": "text", "text": "Found it."},
            ]
        )
        events = mapper.map("updates", {"model": {"messages": [message]}})
        assert events == [
            {
                "t": "tool",
                "id": "ws_1",
                "name": "web_search",
                "args": {"query": "attention is all you need"},
            },
            {"t": "tool_result", "id": "ws_1", "result": {"status": "success"}},
        ]

    def test_a_call_is_announced_once(self) -> None:
        mapper = GraphEventMapper()
        message = AIMessage(
            content="", tool_calls=[{"id": "c1", "name": "ls", "args": {}}]
        )
        first = mapper.map("updates", {"model": {"messages": [message]}})
        second = mapper.map("updates", {"model": {"messages": [message]}})
        assert len(first) == 1 and second == []

    def test_a_history_rewrite_is_not_new_output(self) -> None:
        """deepagents overwrites the message list before the first model call."""
        mapper = GraphEventMapper()
        rewritten = Overwrite(
            [HumanMessage(content="hi"), AIMessage(content="", tool_calls=[{"id": "old", "name": "ls", "args": {}}])]
        )
        payload = {"PatchToolCallsMiddleware.before_agent": {"messages": rewritten}}
        assert mapper.map("updates", payload) == []

    def test_a_single_message_write_is_handled_like_a_list(self) -> None:
        mapper = GraphEventMapper()
        message = ToolMessage(content="ok", tool_call_id="c1")
        assert mapper.map("updates", {"tools": {"messages": message}}) == [
            {"t": "tool_result", "id": "c1", "result": "ok"}
        ]

    def test_non_message_channels_and_unknown_modes_are_ignored(self) -> None:
        mapper = GraphEventMapper()
        assert mapper.map("updates", {"model": {"todos": []}}) == []
        assert mapper.map("updates", {"model": "not a dict"}) == []
        assert mapper.map("values", {"messages": []}) == []


def test_content_blocks_normalises_every_shape() -> None:
    assert content_blocks("hi") == [{"type": "text", "text": "hi"}]
    assert content_blocks("") == []
    assert content_blocks([{"type": "text", "text": "a"}, "stray"]) == [
        {"type": "text", "text": "a"}
    ]
    assert content_blocks(None) == []
