"""A chat thread's history, as the checkpointer keeps it and as the page reads it.

The LangGraph checkpointer is the source of truth for what was said in a thread:
one chat thread is one LangGraph thread, keyed by the ``chat_threads`` row id.
``chat_threads`` itself stays as the index (owner, title, archived), because the
checkpointer has no notion of any of those.

Three concerns live here:

- **Building a turn.** The user's text becomes a ``HumanMessage``; attached
  documents are mounted into the agent's filesystem under ``/attachments/`` and
  pointed at from the message, so the agent reads and greps them with its file
  tools instead of receiving the whole text inline. The original text and the
  attachment list travel in ``additional_kwargs`` so the page can show the
  message the user typed, with chips, rather than the pointer note.
- **Reading state back.** Straight from the saver, without building an agent:
  ``aget_tuple`` hands back the channel values, which is all a page load needs.
- **Serialising for the page.** LangChain messages become the subset of
  ``LangChainMessage`` that ``@assistant-ui/react-langgraph`` renders. Reasoning
  is rewritten from the ``v1`` block layout the model streams in to the
  ``summary`` layout the converter understands, and hosted web search becomes an
  ordinary tool call with a result.
"""

import json
import re
import uuid
from pathlib import Path
from collections.abc import Collection
from typing import Any, Optional, Sequence

from deepagents.backends.utils import create_file_data
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from lib.agents.checkpointer import get_checkpointer
from lib.services.chat.citations import render_citations
from lib.services.chat.events import content_blocks

ATTACHMENTS_DIR = "/attachments"

UiMessage = dict[str, Any]


class ChatAttachment(BaseModel):
    """A document the user attached to the turn, already converted to text."""

    name: str
    text: str = Field(min_length=1)


def thread_config(thread_id: str) -> RunnableConfig:
    """The checkpointer and this are a pair: a checkpointer needs a thread to key by."""

    return {"configurable": {"thread_id": thread_id}}


def attachment_path(name: str, taken: Collection[str] = ()) -> str:
    """Where an attachment is mounted: a filesystem-safe stem, always ``.md``.

    Two attachments in one turn whose names sanitise to the same stem get
    numbered, so neither silently replaces the other.
    """

    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).stem).strip("-.") or "document"
    path = f"{ATTACHMENTS_DIR}/{stem}.md"
    counter = 2
    while path in taken:
        path = f"{ATTACHMENTS_DIR}/{stem}-{counter}.md"
        counter += 1
    return path


def build_user_turn(
    text: str, attachments: Sequence[ChatAttachment], message_id: Optional[str] = None
) -> tuple[HumanMessage, dict[str, Any]]:
    """The message for this turn and the files it mounts.

    Attachments are referenced from the message rather than inlined, so a long
    document does not sit in the prompt of every later turn: it is in the
    filesystem, where the agent reads the parts it needs.

    ``message_id`` is the id the page already shows the message under; the
    checkpointer keeps it, so the stored copy and the local one are one message.
    """

    files: dict[str, Any] = {}
    notes: list[str] = []
    listed: list[dict[str, Any]] = []
    for attachment in attachments:
        path = attachment_path(attachment.name, taken=files)
        files[path] = create_file_data(attachment.text)
        listed.append({"name": attachment.name, "path": path, "chars": len(attachment.text)})
        notes.append(
            f'[Attached document "{attachment.name}" is mounted at {path}. '
            "Read it with your file tools.]"
        )

    user_text = text.strip()
    content = "\n\n".join(part for part in [user_text, *notes] if part)
    message = HumanMessage(
        content=content,
        id=message_id or str(uuid.uuid4()),
        additional_kwargs={"user_text": user_text, "attachments": listed},
    )
    return message, files


async def load_thread_values(thread_id: str) -> dict[str, Any]:
    """The latest checkpoint's channel values, or nothing for a thread never run."""

    async with get_checkpointer() as saver:
        saved = await saver.aget_tuple(thread_config(thread_id))
    if saved is None:
        return {}
    return dict(saved.checkpoint.get("channel_values") or {})


async def load_thread_messages(thread_id: str) -> list[BaseMessage]:
    values = await load_thread_values(thread_id)
    return [m for m in values.get("messages") or [] if isinstance(m, BaseMessage)]


async def read_thread_file(thread_id: str, path: str) -> Optional[str]:
    """A file from the thread's filesystem, joined back into text; None if absent."""

    values = await load_thread_values(thread_id)
    data = (values.get("files") or {}).get(path)
    if not isinstance(data, dict):
        return None
    content = data.get("content")
    if isinstance(content, list):
        return "\n".join(str(line) for line in content)
    return str(content) if content is not None else None


async def delete_thread_state(thread_id: str) -> None:
    async with get_checkpointer() as saver:
        await saver.adelete_thread(thread_id)


def to_ui_messages(messages: Sequence[BaseMessage]) -> list[UiMessage]:
    """The thread as the page renders it. System messages and empty turns are dropped."""

    ui: list[UiMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            ui.append(_human(message))
        elif isinstance(message, AIMessage):
            ui.extend(_ai(message))
        elif isinstance(message, ToolMessage):
            ui.append(_tool(message))
    return ui


def _human(message: HumanMessage) -> UiMessage:
    kwargs = message.additional_kwargs or {}
    text = kwargs.get("user_text")
    return {
        "id": message.id,
        "type": "human",
        "content": text if isinstance(text, str) else message.text,
        "additional_kwargs": {"attachments": list(kwargs.get("attachments") or [])},
    }


def _ai(message: AIMessage) -> list[UiMessage]:
    content: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = [
        {"id": call["id"], "name": call["name"], "args": call.get("args") or {}}
        for call in message.tool_calls
        if call.get("id")
    ]
    results: list[UiMessage] = []

    for block in content_blocks(message.content):
        kind = block.get("type")
        if kind == "text" and block.get("text"):
            _append_text(content, render_citations(block["text"]))
        elif kind == "reasoning":
            summary = _reasoning_text(block)
            if summary:
                content.append(
                    {"type": "reasoning", "summary": [{"type": "summary_text", "text": summary}]}
                )
        elif kind == "server_tool_call" and block.get("id"):
            tool_calls.append(
                {
                    "id": block["id"],
                    "name": block.get("name") or "web_search",
                    "args": block.get("args") or {},
                }
            )
        elif kind == "server_tool_result" and block.get("tool_call_id"):
            call_id = block["tool_call_id"]
            name = next((c["name"] for c in tool_calls if c["id"] == call_id), "web_search")
            status = block.get("status")
            results.append(
                {
                    "id": f"{message.id}:{call_id}",
                    "type": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": json.dumps({"status": status}),
                    "status": "error" if status == "error" else "success",
                }
            )

    if not content and not tool_calls:
        return []
    return [
        {"id": message.id, "type": "ai", "content": content, "tool_calls": tool_calls},
        *results,
    ]


def _tool(message: ToolMessage) -> UiMessage:
    # A ToolMessage built without a name or status would otherwise serialise
    # nulls into a shape the page expects to be strings.
    return {
        "id": message.id,
        "type": "tool",
        "tool_call_id": message.tool_call_id,
        "name": message.name or "tool",
        "content": message.text,
        "status": message.status or "success",
    }


def _append_text(content: list[dict[str, Any]], text: str) -> None:
    if not text:
        return
    if content and content[-1].get("type") == "text":
        content[-1]["text"] += text
    else:
        content.append({"type": "text", "text": text})


def _reasoning_text(block: dict[str, Any]) -> str:
    """Reasoning text from either layout: ``v1``'s string, or a summary list."""

    if isinstance(block.get("reasoning"), str):
        return block["reasoning"]
    summary = block.get("summary")
    if isinstance(summary, list):
        return "".join(
            part.get("text", "") for part in summary if isinstance(part, dict)
        )
    return ""
