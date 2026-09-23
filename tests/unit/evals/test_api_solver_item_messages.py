"""Tests for surfacing backend agent conversations in the Inspect log."""

from unittest.mock import MagicMock, patch

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageTool, ChatMessageUser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from evals_inspectai.common import transcript_replay
from evals_inspectai.common.api_solver import pop_conversations
from evals_inspectai.common.transcript_replay import Conversation, replay_conversation, replay_conversations


def _conversation(start: int, end: int) -> list:
    return [
        SystemMessage(content="skill + guidance"),
        HumanMessage(content=f"Catalogue the abbreviations on lines {start}-{end} of /main.md"),
        AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "/main.md"}}],
            response_metadata={"model_name": "gpt-5.6-terra"},
            usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
        ),
        ToolMessage(content="     1\tThe NATO alliance.", tool_call_id="c1", name="read_file"),
        AIMessage(content='{"occurrences": []}', response_metadata={"model_name": "gpt-5.6-terra"}),
    ]


def _chunk(index: int, status: str, messages: list, **extra) -> dict:
    return {
        "chunk_index": index,
        "start_line": 1 + index * 10,
        "end_line": 10 + index * 10,
        "status": status,
        "occurrences": [],
        "messages": [m.model_dump() for m in messages],
        **extra,
    }


def test_conversations_come_out_in_run_order_and_leave_the_state():
    state = {
        "messages": [m.model_dump() for m in _conversation(1, 1)],
        "chunks": [
            _chunk(0, "completed", _conversation(1, 10)),
            _chunk(1, "skipped", [], skip_reason="abbreviations section"),
            _chunk(2, "partial", _conversation(21, 30), error="cut"),
        ],
    }

    conversations = pop_conversations(state, "abbreviation_scan_v2", "chunks", "chunk")

    assert [c.label for c in conversations] == [
        "abbreviation_scan_v2",
        "chunk 0 · lines 1-10",
        "chunk 2 · lines 21-30 · partial",
    ]
    assert conversations[2].metadata == {
        "chunks": {"index": 2, "lines": "21-30", "status": "partial", "error": "cut"}
    }
    assert "messages" not in state
    assert all("messages" not in chunk for chunk in state["chunks"])


def test_without_an_item_key_only_the_top_level_conversation_is_taken():
    state = {"messages": [m.model_dump() for m in _conversation(1, 1)], "chunks": [_chunk(0, "completed", _conversation(1, 10))]}
    assert [c.label for c in pop_conversations(state, "wf", None)] == ["wf"]
    assert "messages" in state["chunks"][0]


async def _replay(as_sub_agent: bool):
    recorder = MagicMock()
    conversation = Conversation(label="chunks 0 · lines 1-10", metadata={"chunks": {"index": 0}}, messages=_conversation(1, 10))
    with (
        patch.object(transcript_replay, "transcript", return_value=recorder),
        patch.object(transcript_replay, "span", wraps=transcript_replay.span) as span_spy,
    ):
        messages = await replay_conversation(conversation, as_sub_agent=as_sub_agent)
    return messages, [c.args[0] for c in recorder._event.call_args_list], span_spy


@pytest.mark.asyncio
async def test_replay_records_one_model_event_per_assistant_turn_with_its_full_input():
    messages, events, _ = await _replay(as_sub_agent=False)

    assert all(isinstance(e, ModelEvent) for e in events)
    assert [len(e.input) for e in events] == [2, 4]
    assert isinstance(events[0].input[0], ChatMessageSystem)  # the system prompt is part of every call's input
    assert events[0].output.choices[0].stop_reason == "tool_calls"
    assert events[1].output.choices[0].stop_reason == "stop"
    assert events[0].model == "gpt-5.6-terra"
    assert events[0].output.usage is not None and events[0].output.usage.total_tokens == 110

    assert [type(m) for m in messages] == [ChatMessageSystem, ChatMessageUser, ChatMessageAssistant, ChatMessageTool, ChatMessageAssistant]
    assert messages[0].metadata == {"chunks": {"index": 0}}


@pytest.mark.asyncio
async def test_main_conversation_is_not_grouped_but_a_sub_agent_is():
    _, main_events, main_span = await _replay(as_sub_agent=False)
    _, sub_events, sub_span = await _replay(as_sub_agent=True)

    assert main_span.call_count == 0 and len(main_events) == 2
    assert sub_span.call_count == 1 and len(sub_events) == 2
    assert sub_span.call_args.args[0] == "chunks 0 · lines 1-10"


def test_token_usage_survives_the_round_trip_through_the_state():
    state = {"messages": [m.model_dump() for m in _conversation(1, 1)]}
    [conversation] = pop_conversations(state, "wf", None)
    assert conversation.messages[2].usage_metadata["total_tokens"] == 110


@pytest.mark.asyncio
async def test_one_conversation_is_ungrouped_and_fills_the_messages_tab():
    conversation = Conversation(label="wf", messages=_conversation(1, 10))
    with (
        patch.object(transcript_replay, "transcript", return_value=MagicMock()),
        patch.object(transcript_replay, "span", wraps=transcript_replay.span) as span_spy,
    ):
        messages = await replay_conversations([conversation])
    assert span_spy.call_count == 0
    assert len(messages) == 5


@pytest.mark.asyncio
async def test_several_conversations_are_all_grouped_alike_and_leave_the_messages_tab():
    conversations = [Conversation(label=f"section {i}", messages=_conversation(1, 10)) for i in range(3)]
    with (
        patch.object(transcript_replay, "transcript", return_value=MagicMock()),
        patch.object(transcript_replay, "span", wraps=transcript_replay.span) as span_spy,
    ):
        messages = await replay_conversations(conversations)
    assert [c.args[0] for c in span_spy.call_args_list] == ["section 0", "section 1", "section 2"]
    assert messages == []
