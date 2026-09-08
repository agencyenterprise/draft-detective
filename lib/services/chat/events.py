"""LangGraph stream output, mapped to the events the /chat page renders.

The page understands these events: ``message`` and ``message_end`` marking an
assistant message and carrying the id it is checkpointed under, ``text`` and
``reasoning`` deltas, a ``tool`` call with its complete arguments, a
``tool_result`` (with the id of the stored tool message), and an ``error``. The
ids matter: the page shows a turn from these events while it streams and from
the checkpointer afterwards, and the same ids are what stop assistant-ui from
treating the two as different messages. This module produces them from a graph
streamed with ``stream_mode=["messages", "updates"]``:

- ``messages`` carries the model's token stream. Text and reasoning deltas come
  from there, read off the ``v1`` content blocks (see ``build_llm``).
- ``updates`` carries each node's finished output. Tool calls are announced
  from the completed ``AIMessage``, once their arguments are whole, and tool
  results from the ``ToolMessage`` the tools node wrote. Hosted web search never
  produces a ``ToolMessage``; its call and result are content blocks on the
  ``AIMessage`` itself.

Ordering follows from that split: a message opens with its first streamed chunk,
its text streams, then the completed message announces its tool calls and
closes, then the tool results arrive, then the next message opens.

The persisted id of an assistant message is the id of the first chunk the model
streamed for it (later chunks carry a different, per-run id). ``message`` uses
that; ``message_end`` repeats the final id so the page can correct itself if the
two ever differ.
"""

import uuid
from typing import Any, AsyncIterator, Iterable, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite, StreamMode

from lib.services.chat.citations import CitationFilter

ChatEvent = dict[str, Any]

STREAM_MODES: list[StreamMode] = ["messages", "updates"]


def message_event(message_id: str) -> ChatEvent:
    return {"t": "message", "id": message_id}


def message_end_event(message_id: str) -> ChatEvent:
    return {"t": "message_end", "id": message_id}


def text_event(delta: str) -> ChatEvent:
    return {"t": "text", "v": delta}


def reasoning_event(delta: str) -> ChatEvent:
    return {"t": "reasoning", "v": delta}


def tool_event(call_id: str, name: str, args: Any) -> ChatEvent:
    return {"t": "tool", "id": call_id, "name": name, "args": args}


def tool_result_event(
    call_id: str, result: Any, is_error: bool = False, message_id: Optional[str] = None
) -> ChatEvent:
    event: ChatEvent = {"t": "tool_result", "id": call_id, "result": result}
    if is_error:
        event["isError"] = True
    if message_id:
        event["mid"] = message_id
    return event


def error_event(message: str) -> ChatEvent:
    return {"t": "error", "v": message}


def content_blocks(content: Any) -> list[dict[str, Any]]:
    """A message's content as a list of typed blocks, whatever shape it came in."""

    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if isinstance(content, list):
        return [block for block in content if isinstance(block, dict)]
    return []


def new_messages(channel_value: Any) -> list[BaseMessage]:
    """The messages a node appended, from whatever it wrote to the channel.

    A node may write one message or a list. deepagents' ``PatchToolCallsMiddleware``
    instead writes an ``Overwrite`` of the whole history before the first model
    call; that is a rewrite of what the client already sent, not new output, so it
    is skipped rather than re-announced.
    """

    if isinstance(channel_value, Overwrite):
        return []
    if isinstance(channel_value, BaseMessage):
        return [channel_value]
    if isinstance(channel_value, list):
        return [message for message in channel_value if isinstance(message, BaseMessage)]
    return []


class GraphEventMapper:
    """Stateful mapper: tracks the open assistant message and announced tool calls.

    A hosted tool call can show up both in the model's content blocks and, on
    some providers, in ``tool_calls``; the set keeps it to one announcement.
    """

    def __init__(self) -> None:
        self._announced: set[str] = set()
        self._open_message_id: Optional[str] = None
        self._citations = CitationFilter()

    def map(self, mode: str, payload: Any) -> list[ChatEvent]:
        if mode == "messages":
            return self._from_token_stream(payload)
        if mode == "updates":
            return self._from_update(payload)
        return []

    def _from_token_stream(self, payload: Any) -> list[ChatEvent]:
        message = payload[0] if isinstance(payload, (tuple, list)) and payload else None
        if not isinstance(message, AIMessageChunk):
            return []
        events: list[ChatEvent] = self._open(message.id)
        for block in content_blocks(message.content):
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                # Citation markers span several tokens; the filter holds text back
                # until a marker is whole, so a delta may come out empty for now.
                text = self._citations.feed(block["text"])
                if text:
                    events.append(text_event(text))
            elif kind == "reasoning" and block.get("reasoning"):
                events.append(reasoning_event(block["reasoning"]))
        return events

    def _from_update(self, payload: Any) -> list[ChatEvent]:
        if not isinstance(payload, dict):
            return []
        events: list[ChatEvent] = []
        for channels in payload.values():
            if not isinstance(channels, dict):
                continue
            for message in new_messages(channels.get("messages")):
                if isinstance(message, AIMessage):
                    events.extend(self._from_ai_message(message))
                elif isinstance(message, ToolMessage):
                    events.append(self._from_tool_message(message))
        return events

    def _from_ai_message(self, message: AIMessage) -> list[ChatEvent]:
        events: list[ChatEvent] = self._open(message.id)
        for call in message.tool_calls:
            call_id = call.get("id")
            if call_id:
                events.extend(self._announce(call_id, call["name"], call.get("args") or {}))
        for block in content_blocks(message.content):
            kind, call_id = block.get("type"), block.get("id") or block.get("tool_call_id")
            if not call_id:
                continue
            if kind == "server_tool_call":
                name = block.get("name") or "web_search"
                events.extend(self._announce(call_id, name, block.get("args") or {}))
            elif kind == "server_tool_result":
                status = block.get("status")
                events.append(
                    tool_result_event(
                        call_id,
                        {"status": status},
                        is_error=status == "error",
                        message_id=f"{message.id}:{call_id}",
                    )
                )
        held_back = self._citations.flush()
        if held_back:
            events.append(text_event(held_back))
        events.append(message_end_event(message.id or self._open_message_id or ""))
        self._open_message_id = None
        return events

    def _open(self, message_id: Optional[str]) -> list[ChatEvent]:
        """Announce an assistant message once, under the id it will be stored as."""

        if self._open_message_id is not None:
            return []
        self._open_message_id = message_id or str(uuid.uuid4())
        self._citations = CitationFilter()
        return [message_event(self._open_message_id)]

    def _announce(self, call_id: str, name: str, args: Any) -> Iterable[ChatEvent]:
        if call_id in self._announced:
            return ()
        self._announced.add(call_id)
        return (tool_event(call_id, name, args),)

    @staticmethod
    def _from_tool_message(message: ToolMessage) -> ChatEvent:
        return tool_result_event(
            message.tool_call_id,
            message.text,
            is_error=message.status == "error",
            message_id=message.id,
        )


async def stream_chat_events(
    agent: CompiledStateGraph,
    agent_input: dict[str, Any],
    config: RunnableConfig,
) -> AsyncIterator[ChatEvent]:
    """Run one turn and yield the page's events as the graph produces them."""

    mapper = GraphEventMapper()
    async for mode, payload in agent.astream(
        agent_input, config=config, stream_mode=STREAM_MODES
    ):
        for event in mapper.map(mode, payload):
            yield event
