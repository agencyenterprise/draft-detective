"""Before each turn of a shared thread, take out what the person asking cannot read.

One Teams conversation is one LangGraph thread, so a document opened for A is still
mounted when B asks next, and A's reads of it are still in the history. Telling the
model to call ``check_document`` first is not enough: B can tell it not to. So the
check is made here, in code, before the model sees B's question.

Every document ``open_document`` mounted is looked up again as the person asking now.
When all of them answer, nothing changes: a shared thread stays shared for everyone who
can read what it holds. When one does not, that person must not get it from this
thread, by any route:

- every file goes but the packaged skills: the copies, their comments and anything the agent
  wrote itself, which may have been made from one. The readable copies go too, because
  the history that recorded where each came from goes next, and a copy whose link is
  forgotten could never be checked again;
- so do the images those copies named, which ``view_image`` would otherwise still serve
  to anyone in the conversation who has a reference to one;
- the history is cut back to what was said in the chat itself, the questions and the
  answers posted, since the agent's working (tool calls, the text they returned, its
  reasoning) may quote it.

A lookup that fails for any reason counts as a refusal. A copy taken out by mistake
costs the next person who can read it one ``open_document``; a copy left in by mistake
cannot be taken back.
"""

import asyncio
import logging
import uuid
from collections.abc import Collection, Mapping, Sequence
from typing import Any, cast

from deepagents.backends.protocol import FileData
from deepagents.backends.utils import file_data_to_string
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)

from lib.agents.tools.sharepoint import OPENED
from lib.services.files import images as file_images
from lib.services.microsoft.graph import client
from lib.services.microsoft.graph.client import redacted

logger = logging.getLogger(__name__)


def opened_links(messages: Sequence[BaseMessage]) -> set[str]:
    """Every link the thread has opened a document from, still mounted or not.

    Not only those mounted now: a copy replaced at the same path, or deleted, still
    has its reads in the history. Read from the history rather than from the files: the
    agent can write any file, but not a tool call, so nothing can claim a link it was
    not opened from.
    """

    opened = {
        m.tool_call_id
        for m in messages
        if isinstance(m, ToolMessage) and str(m.content).startswith(OPENED)
    }
    return {
        str(call["args"].get("url"))
        for m in messages
        if isinstance(m, AIMessage)
        for call in m.tool_calls
        if call["name"] == "open_document" and call["id"] in opened
    }


async def _can_read(url: str, token: str) -> bool:
    try:
        await client.resolve(url, token=token)
    except Exception as error:  # noqa: BLE001 - any failure withholds the copy
        logger.info("withholding %s from this asker: %s", redacted(url), error)
        return False
    return True


async def all_readable(messages: Sequence[BaseMessage], token: str) -> bool:
    """Whether ``token`` can read every document the thread has opened."""

    urls = opened_links(messages)
    return all(await asyncio.gather(*(_can_read(url, token) for url in urls)))


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
    state: Mapping[str, Any],
    token: str,
    conversation_id: uuid.UUID,
    skills: Collection[str],
) -> tuple[dict[str, None], list[BaseMessage]]:
    """The file deletions and history updates that keep this turn to what ``token``
    can read, with the images the deleted files named dropped from ``conversation_id``.
    Both empty, and nothing dropped, when it can read every document the thread opened.

    ``skills`` are the packaged skill files, the only ones kept: the agent can write
    under ``/skills/`` too, and a skill it edited is mounted again from the package.
    """

    files: Mapping[str, Any] = state.get("files") or {}
    messages = [m for m in state.get("messages") or [] if isinstance(m, BaseMessage)]
    if await all_readable(messages, token):
        return {}, []

    withheld = {
        path: cast(FileData, data)
        for path, data in files.items()
        if isinstance(data, dict) and path not in skills
    }
    images = set().union(
        *(
            file_images.referenced_images(file_data_to_string(d))
            for d in withheld.values()
        )
    )
    await file_images.drop_conversation_images(conversation_id, images)
    return dict.fromkeys(withheld), public_history(messages)
