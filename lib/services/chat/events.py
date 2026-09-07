"""LangGraph stream output, mapped to the events the /chat page renders.

The page understands five events, unchanged from when a Next.js route produced
them: ``text`` and ``reasoning`` deltas, a ``tool`` call with its complete
arguments, a ``tool_result``, and an ``error``. This module produces them from
a graph streamed with ``stream_mode=["messages", "updates"]``:

- ``messages`` carries the model's token stream. Text and reasoning deltas come
  from there, read off the ``v1`` content blocks (see ``build_llm``).
- ``updates`` carries each node's finished output. Tool calls are announced
  from the completed ``AIMessage``, once their arguments are whole, and tool
  results from the ``ToolMessage`` the tools node wrote. Hosted web search never
  produces a ``ToolMessage``; its call and result are content blocks on the
  ``AIMessage`` itself.

Ordering follows from that split: a turn's text streams first, then its tool
calls are announced, then the results arrive, then the next model turn streams.
"""

from typing import Any, AsyncIterator, Iterable

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite, StreamMode

ChatEvent = dict[str, Any]

STREAM_MODES: list[StreamMode] = ["messages", "updates"]


def text_event(delta: str) -> ChatEvent:
    return {"t": "text", "v": delta}


def reasoning_event(delta: str) -> ChatEvent:
    return {"t": "reasoning", "v": delta}


def tool_event(call_id: str, name: str, args: Any) -> ChatEvent:
    return {"t": "tool", "id": call_id, "name": name, "args": args}


def tool_result_event(call_id: str, result: Any, is_error: bool = False) -> ChatEvent:
    event: ChatEvent = {"t": "tool_result", "id": call_id, "result": result}
    if is_error:
        event["isError"] = True
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
    """Stateful mapper: remembers which tool calls it has already announced.

    A hosted tool call can show up both in the model's content blocks and, on
    some providers, in ``tool_calls``; the set keeps it to one announcement.
    """

    def __init__(self) -> None:
        self._announced: set[str] = set()

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
        events: list[ChatEvent] = []
        for block in content_blocks(message.content):
            kind = block.get("type")
            if kind == "text" and block.get("text"):
                events.append(text_event(block["text"]))
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
        events: list[ChatEvent] = []
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
                    tool_result_event(call_id, {"status": status}, is_error=status == "error")
                )
        return events

    def _announce(self, call_id: str, name: str, args: Any) -> Iterable[ChatEvent]:
        if call_id in self._announced:
            return ()
        self._announced.add(call_id)
        return (tool_event(call_id, name, args),)

    @staticmethod
    def _from_tool_message(message: ToolMessage) -> ChatEvent:
        return tool_result_event(
            message.tool_call_id, message.text, is_error=message.status == "error"
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
