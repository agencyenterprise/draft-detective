"""Before each turn of a shared thread, take out what the person asking cannot read.

One Teams conversation is one LangGraph thread, so a document opened for A is still
mounted when B asks next, and A's reads of it are still in the history. Telling the
model to call ``check_document`` first is not enough: B can tell it not to. So the
check is made here, in code, before the model sees B's question.

Every document ``open_document`` mounted is looked up again as the person asking now.
When all of them answer, nothing changes: a shared thread stays shared for everyone who
can read what it holds. When one does not, that person must not get it from this
thread, by any route:

- its copy and comments go, and so does every file the agent wrote itself, which may
  have been made from it;
- the history is cut back to what was said in the chat itself, the questions and the
  answers posted, since the agent's working (tool calls, the text they returned, its
  reasoning) may quote it.

A lookup that fails for any reason counts as a refusal. A copy taken out by mistake
costs the next person who can read it one ``open_document``; a copy left in by mistake
cannot be taken back.
"""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)

from lib.agents.tools.sharepoint import OPENED, comments_path, document_path
from lib.services.microsoft.graph import client
from lib.services.microsoft.graph.client import redacted

logger = logging.getLogger(__name__)

SKILLS = "/skills/"


def opened_documents(messages: Sequence[BaseMessage]) -> dict[str, str]:
    """Each mounted document's path and the link it was opened from; the latest wins.

    Read from the history rather than from the files: the agent can write any file, but
    not a tool call, so a path cannot be made to claim a link it was not opened from.
    """

    opened = {
        m.tool_call_id
        for m in messages
        if isinstance(m, ToolMessage) and str(m.content).startswith(OPENED)
    }
    sources: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            if call["name"] != "open_document" or call["id"] not in opened:
                continue
            try:
                sources[document_path(str(call["args"]["path"]))] = str(
                    call["args"]["url"]
                )
            except (KeyError, ValueError):
                continue
    return sources


async def _can_read(url: str, token: str) -> bool:
    try:
        await client.resolve(url, token=token)
    except Exception as error:  # noqa: BLE001 - any failure withholds the copy
        logger.info("withholding %s from this asker: %s", redacted(url), error)
        return False
    return True


async def readable_documents(
    files: Mapping[str, Any], messages: Sequence[BaseMessage], token: str
) -> tuple[set[str], set[str]]:
    """The mounted documents ``token`` can read, and those it cannot."""

    mounted = {
        path: url
        for path, url in opened_documents(messages).items()
        if files.get(path) is not None
    }
    urls = sorted(set(mounted.values()))
    answers = await asyncio.gather(*(_can_read(url, token) for url in urls))
    readable = {url for url, ok in zip(urls, answers, strict=True) if ok}
    return (
        {path for path, url in mounted.items() if url in readable},
        {path for path, url in mounted.items() if url not in readable},
    )


def public_history(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """The updates that cut a history back to what was said in the chat.

    Questions stay. An answer stays as its text, without the reasoning that came with
    it. Everything else -- tool calls and what they returned -- is removed.
    """

    updates: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage) or message.id is None:
            continue
        if isinstance(message, AIMessage) and not message.tool_calls:
            text = str(message.text)
            if message.content != text:
                updates.append(AIMessage(content=text, id=message.id))
            continue
        updates.append(RemoveMessage(id=message.id))
    return updates


async def withhold_unreadable(
    state: Mapping[str, Any], token: str
) -> tuple[dict[str, None], list[BaseMessage]]:
    """The file deletions and history updates that keep this turn to what ``token``
    can read. Both empty when it can read every document the thread holds."""

    files: Mapping[str, Any] = state.get("files") or {}
    messages = [m for m in state.get("messages") or [] if isinstance(m, BaseMessage)]
    readable, unreadable = await readable_documents(files, messages, token)
    if not unreadable:
        return {}, []

    keep = readable | {comments_path(path) for path in readable}
    deletions = {
        path: None
        for path, data in files.items()
        if data is not None and not path.startswith(SKILLS) and path not in keep
    }
    return deletions, public_history(messages)
