"""Reading a chat thread's state back from the checkpointer, and deleting it.

Read through the compiled chat graph rather than the raw checkpoint. deepagents
keeps `messages` and `files` in delta channels, so a checkpoint's channel values
hold only what that step wrote; the graph replays the thread's checkpoints into
its full state. Reading `channel_values` directly returns an empty history for any
thread that ran a turn since.
"""

from typing import Any, Optional, cast

from deepagents.backends.protocol import FileData
from deepagents.backends.utils import file_data_to_string
from langchain_core.messages import BaseMessage

from lib.agents.chat_agent import DEFAULT_CHAT_MODEL, build_chat_agent
from lib.agents.checkpointer import get_checkpointer
from lib.services.chat.history import thread_config

# The reader graph never calls its model, but building one constructs the client,
# which wants a key. A placeholder keeps reads from depending on a configured one.
_READER_API_KEY = "unused-state-reader"


async def load_thread_values(thread_id: str) -> dict[str, Any]:
    """The thread's current state values, or nothing for a thread never run."""

    async with get_checkpointer() as saver:
        reader = build_chat_agent(DEFAULT_CHAT_MODEL, _READER_API_KEY, saver)
        snapshot = await reader.aget_state(thread_config(thread_id))
    return dict(snapshot.values or {})


async def load_thread_messages(thread_id: str) -> list[BaseMessage]:
    values = await load_thread_values(thread_id)
    return [m for m in values.get("messages") or [] if isinstance(m, BaseMessage)]


async def read_thread_file(thread_id: str, path: str) -> Optional[str]:
    """A file from the thread's filesystem as text; None if absent."""

    values = await load_thread_values(thread_id)
    data = (values.get("files") or {}).get(path)
    if not isinstance(data, dict):
        return None
    return file_data_to_string(cast(FileData, data))


async def delete_thread_state(thread_id: str) -> None:
    async with get_checkpointer() as saver:
        await saver.adelete_thread(thread_id)
