"""Reading a chat thread's state back from the checkpointer, and deleting it.

Read through a compiled graph rather than the raw checkpoint. deepagents keeps
`messages` and `files` in delta channels, so a checkpoint's channel values hold only
what that step wrote; the graph replays the thread's checkpoints into its full state.
Reading `channel_values` directly returns an empty history for any thread that ran a
turn since.

The graph that replays a thread is the one that wrote it, so each reader names its
own (``chat_reader`` for /chat, ``word_chat_reader`` for the Word pane, each next
to its agent): a graph is
never asked to read state shaped by another agent's tools and middleware.
"""

from collections.abc import Callable
from typing import Any, cast

from deepagents.backends.protocol import FileData
from deepagents.backends.utils import file_data_to_string
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from lib.agents.checkpointer import get_checkpointer
from lib.services.chat.history import thread_config

# Builds the graph a thread is replayed through, over the checkpointer it reads from.
ThreadReader = Callable[[BaseCheckpointSaver], CompiledStateGraph]

# A reader graph never calls its model, but building one constructs the client,
# which wants a key. A placeholder keeps reads from depending on a configured one.
READER_API_KEY = "unused-state-reader"


async def load_thread_snapshot(
    thread_id: str, *, reader: ThreadReader
) -> StateSnapshot:
    """The thread's current state, interrupts included; empty for a thread never run."""

    async with get_checkpointer() as saver:
        return await reader(saver).aget_state(thread_config(thread_id))


async def load_thread_values(thread_id: str, *, reader: ThreadReader) -> dict[str, Any]:
    """The thread's current state values, or nothing for a thread never run."""

    snapshot = await load_thread_snapshot(thread_id, reader=reader)
    return dict(snapshot.values or {})


async def load_thread_messages(
    thread_id: str, *, reader: ThreadReader
) -> list[BaseMessage]:
    values = await load_thread_values(thread_id, reader=reader)
    return [m for m in values.get("messages") or [] if isinstance(m, BaseMessage)]


async def read_thread_file(
    thread_id: str, path: str, *, reader: ThreadReader
) -> str | None:
    """A file from the thread's filesystem as text; None if absent."""

    values = await load_thread_values(thread_id, reader=reader)
    data = (values.get("files") or {}).get(path)
    if not isinstance(data, dict):
        return None
    return file_data_to_string(cast(FileData, data))


async def delete_thread_state(thread_id: str) -> None:
    async with get_checkpointer() as saver:
        await saver.adelete_thread(thread_id)
