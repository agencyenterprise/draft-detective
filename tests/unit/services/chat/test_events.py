"""The graph stream, mapped to the five events the /chat page renders.

Chunk shapes here mirror what langchain-openai emits under ``output_version="v1"``
through a deep agent (captured in a spike before this was written): text and
reasoning content blocks in the token stream, ``tool_call_chunk`` blocks that
are deliberately ignored there, and completed messages in ``updates``.
"""

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Interrupt, Overwrite

from lib.services.chat.events import GraphEventMapper, content_blocks


def _tokens(*blocks: dict, id: str = "resp_1") -> tuple:
    return (AIMessageChunk(content=list(blocks), id=id), {"langgraph_node": "model"})


def _without_boundaries(events: list[dict]) -> list[dict]:
    return [e for e in events if e["t"] not in ("message", "message_end")]


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
            {"t": "message", "id": "resp_1"},
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
        assert _without_boundaries(events) == []

    def test_string_content_is_a_text_delta(self) -> None:
        mapper = GraphEventMapper()
        chunk: tuple[AIMessageChunk, dict] = (
            AIMessageChunk(content="plain", id="resp_1"),
            {},
        )
        assert mapper.map("messages", chunk) == [
            {"t": "message", "id": "resp_1"},
            {"t": "text", "v": "plain"},
        ]

    def test_tool_messages_in_the_token_stream_are_ignored(self) -> None:
        """They are handled from ``updates``; doing both would double them."""
        mapper = GraphEventMapper()
        payload: tuple[ToolMessage, dict] = (
            ToolMessage(content="result", tool_call_id="c1"),
            {},
        )
        assert mapper.map("messages", payload) == []


class TestMessageBoundaries:
    def test_a_message_opens_on_its_first_chunk_and_closes_when_complete(self) -> None:
        """The persisted id is the first chunk's; later chunks carry a run id."""
        mapper = GraphEventMapper()
        first = mapper.map("messages", _tokens(id="resp_1"))
        text = mapper.map(
            "messages", _tokens({"type": "text", "text": "Hi"}, id="lc_run--1")
        )
        done = mapper.map(
            "updates", {"model": {"messages": [AIMessage(content="Hi", id="resp_1")]}}
        )
        assert first == [{"t": "message", "id": "resp_1"}]
        assert text == [{"t": "text", "v": "Hi"}]
        assert done == [{"t": "message_end", "id": "resp_1"}]

    def test_the_next_model_turn_opens_a_new_message(self) -> None:
        mapper = GraphEventMapper()
        mapper.map("messages", _tokens(id="resp_1"))
        mapper.map(
            "updates",
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            id="resp_1",
                            tool_calls=[{"id": "c1", "name": "ls", "args": {}}],
                        )
                    ]
                }
            },
        )
        mapper.map(
            "updates",
            {
                "tools": {
                    "messages": [ToolMessage(content="x", tool_call_id="c1", id="t1")]
                }
            },
        )
        assert mapper.map("messages", _tokens(id="resp_2")) == [
            {"t": "message", "id": "resp_2"}
        ]

    def test_a_message_that_never_streamed_still_opens_and_closes(self) -> None:
        mapper = GraphEventMapper()
        events = mapper.map(
            "updates",
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            id="resp_9",
                            tool_calls=[{"id": "c1", "name": "ls", "args": {}}],
                        )
                    ]
                }
            },
        )
        assert [e["t"] for e in events] == ["message", "tool", "message_end"]
        assert events[0]["id"] == events[2]["id"] == "resp_9"

    def test_a_chunk_without_an_id_gets_one(self) -> None:
        mapper = GraphEventMapper()
        (opened,) = mapper.map("messages", (AIMessageChunk(content=""), {}))
        assert opened["t"] == "message" and opened["id"]


class TestUpdates:
    def test_completed_tool_calls_are_announced_with_whole_args(self) -> None:
        mapper = GraphEventMapper()
        message = AIMessage(
            content="",
            id="resp_1",
            tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "/a"}}],
        )
        events = mapper.map("updates", {"model": {"messages": [message]}})
        assert _without_boundaries(events) == [
            {"t": "tool", "id": "c1", "name": "read_file", "args": {"file_path": "/a"}}
        ]

    def test_a_tool_message_a_middleware_rewrites_is_not_a_new_result(self) -> None:
        # SeenImageRedactionMiddleware replaces a seen image result under the same id.
        mapper = GraphEventMapper()
        redacted = ToolMessage(content="[image seen]", tool_call_id="c1", id="t1")
        update = {"SeenImageRedactionMiddleware.after_model": {"messages": [redacted]}}
        assert mapper.map("updates", update) == []

    def test_a_tool_message_is_a_result_carrying_its_stored_id(self) -> None:
        mapper = GraphEventMapper()
        ok = ToolMessage(content="contents", tool_call_id="c1", id="t1")
        failed = ToolMessage(content="boom", tool_call_id="c2", status="error", id="t2")
        events = mapper.map("updates", {"tools": {"messages": [ok, failed]}})
        assert events == [
            {"t": "tool_result", "id": "c1", "result": "contents", "mid": "t1"},
            {
                "t": "tool_result",
                "id": "c2",
                "result": "boom",
                "isError": True,
                "mid": "t2",
            },
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
                {
                    "type": "server_tool_result",
                    "tool_call_id": "ws_1",
                    "status": "success",
                },
                {"type": "text", "text": "Found it."},
            ]
        )
        events = mapper.map("updates", {"model": {"messages": [message]}})
        assert _without_boundaries(events) == [
            {
                "t": "tool",
                "id": "ws_1",
                "name": "web_search",
                "args": {"query": "attention is all you need"},
            },
            {
                "t": "tool_result",
                "id": "ws_1",
                "result": {"status": "success"},
                "mid": f"{message.id}:ws_1",
            },
        ]

    def test_a_call_is_announced_once(self) -> None:
        mapper = GraphEventMapper()
        message = AIMessage(
            content="", tool_calls=[{"id": "c1", "name": "ls", "args": {}}]
        )
        first = mapper.map("updates", {"model": {"messages": [message]}})
        second = mapper.map("updates", {"model": {"messages": [message]}})
        assert (
            len(_without_boundaries(first)) == 1 and _without_boundaries(second) == []
        )

    def test_a_history_rewrite_is_not_new_output(self) -> None:
        """deepagents overwrites the message list before the first model call."""
        mapper = GraphEventMapper()
        rewritten = Overwrite(
            [
                HumanMessage(content="hi"),
                AIMessage(
                    content="", tool_calls=[{"id": "old", "name": "ls", "args": {}}]
                ),
            ]
        )
        payload = {"PatchToolCallsMiddleware.before_agent": {"messages": rewritten}}
        assert mapper.map("updates", payload) == []

    def test_a_history_rewrite_by_removal_is_not_new_output(self) -> None:
        """deepagents 0.7 rewrites it as "remove every message, then these", when a
        tool call was left without a result: a message sent while an answer waited on
        a card. Announcing it would replay the whole conversation's tool calls."""
        mapper = GraphEventMapper()
        rewritten = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"id": "old", "name": "ls", "args": {}}]),
            ToolMessage(content="ok", tool_call_id="old", id="t-old"),
        ]
        payload = {"PatchToolCallsMiddleware.before_agent": {"messages": rewritten}}
        assert mapper.map("updates", payload) == []

    def test_the_model_nodes_reply_after_a_repaired_history_is_new_output(
        self,
    ) -> None:
        """langchain 1.4.3+ answers a malformed tool call with an error result, then
        writes the repaired history followed by the model's reply. The history is
        old; the reply is what the client is waiting for."""
        mapper = GraphEventMapper()
        mapper.map("updates", {"model": {"messages": [AIMessage(content="", id="a1")]}})
        rewritten = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            HumanMessage(content="hi", id="h1"),
            AIMessage(
                content="",
                id="a1",
                tool_calls=[{"id": "old", "name": "ls", "args": {}}],
                invalid_tool_calls=[
                    {"id": "bad", "name": "ls", "args": '{"x', "error": "json"}
                ],
            ),
            ToolMessage(content="bad args", tool_call_id="bad", status="error"),
            ToolMessage(content="ok", tool_call_id="old", id="t-old"),
            AIMessage(
                content="",
                id="a2",
                tool_calls=[{"id": "new", "name": "ls", "args": {}}],
            ),
        ]
        events = mapper.map("updates", {"model": {"messages": rewritten}})
        assert events == [
            {"t": "message", "id": "a2"},
            {"t": "tool", "id": "new", "name": "ls", "args": {}},
            {"t": "message_end", "id": "a2"},
        ]

    def test_a_single_message_write_is_handled_like_a_list(self) -> None:
        mapper = GraphEventMapper()
        message = ToolMessage(content="ok", tool_call_id="c1", id="t1")
        assert mapper.map("updates", {"tools": {"messages": message}}) == [
            {"t": "tool_result", "id": "c1", "result": "ok", "mid": "t1"}
        ]

    def test_non_message_channels_and_unknown_modes_are_ignored(self) -> None:
        mapper = GraphEventMapper()
        assert mapper.map("updates", {"model": {"todos": []}}) == []
        assert mapper.map("updates", {"model": "not a dict"}) == []
        assert mapper.map("updates", "not a dict at all") == []
        assert mapper.map("messages", "not a tuple") == []
        assert mapper.map("values", {"messages": []}) == []


def test_content_blocks_normalises_every_shape() -> None:
    assert content_blocks("hi") == [{"type": "text", "text": "hi"}]
    assert content_blocks("") == []
    assert content_blocks([{"type": "text", "text": "a"}, "stray"]) == [
        {"type": "text", "text": "a"}
    ]
    assert content_blocks(None) == []


class TestAPauseForThePerson:
    def test_an_interrupt_becomes_an_event_with_what_was_asked(self) -> None:
        mapper = GraphEventMapper()
        paused = (Interrupt(value={"suggestion_id": "card-1"}, id="i-1"),)

        events = mapper.map("updates", {"__interrupt__": paused})

        assert events == [{"t": "interrupt", "v": [{"suggestion_id": "card-1"}]}]


class TestAToolResultNamesItsTool:
    def test_the_name_travels_with_the_result(self) -> None:
        """A resumed run's first result answers a call made before it paused, which the
        page has only in the stored history: without the name it cannot match them."""

        mapper = GraphEventMapper()
        message = ToolMessage(
            content="Applied 7 of 8.", tool_call_id="c9", name="ask_to_apply", id="t9"
        )

        events = mapper.map("updates", {"tools": {"messages": [message]}})

        assert events[-1] == {
            "t": "tool_result",
            "id": "c9",
            "result": "Applied 7 of 8.",
            "mid": "t9",
            "name": "ask_to_apply",
        }
