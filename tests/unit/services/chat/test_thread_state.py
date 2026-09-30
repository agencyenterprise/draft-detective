"""Reading a chat thread back from the checkpointer, through the graph.

Runs a real deep agent over an in-memory saver: its `messages` and `files`
channels checkpoint deltas, so a thread that ran more than one turn is where a
reader of raw channel values would come back empty.
"""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from lib.agents.deep_agent_setup import agent_input
from lib.services.chat import thread_state
from lib.services.chat.history import thread_config


class _FakeModel(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> "_FakeModel":
        return self


def _patched(saver: InMemorySaver):
    @asynccontextmanager
    async def get_checkpointer():
        yield saver

    def build_chat_agent(model: Any, api_key: Any, checkpointer: Any) -> Any:
        return create_deep_agent(model=_FakeModel(messages=iter([])), checkpointer=checkpointer)

    return (
        patch.object(thread_state, "get_checkpointer", get_checkpointer),
        patch.object(thread_state, "build_chat_agent", build_chat_agent),
    )


async def _run_turns(saver: InMemorySaver, thread_id: str) -> None:
    replies = iter([AIMessage(content="one"), AIMessage(content="two")])
    agent = create_deep_agent(model=_FakeModel(messages=replies), checkpointer=saver)
    config = thread_config(thread_id)
    await agent.ainvoke(
        agent_input(files={"/attachments/a.md": create_file_data("one\ntwo")}, messages=[HumanMessage("first")]),
        config=config,
    )
    await agent.ainvoke({"messages": [HumanMessage("second")]}, config=config)


@pytest.mark.asyncio
async def test_a_thread_of_several_turns_reads_back_whole() -> None:
    saver = InMemorySaver()
    await _run_turns(saver, "t-1")
    reader, graph = _patched(saver)
    with reader, graph:
        messages = await thread_state.load_thread_messages("t-1")
        attachment = await thread_state.read_thread_file("t-1", "/attachments/a.md")
        missing = await thread_state.read_thread_file("t-1", "/attachments/missing.md")
    assert [m.text for m in messages] == ["first", "one", "second", "two"]
    assert attachment == "one\ntwo"
    assert missing is None


@pytest.mark.asyncio
async def test_a_thread_never_run_has_no_messages() -> None:
    reader, graph = _patched(InMemorySaver())
    with reader, graph:
        assert await thread_state.load_thread_messages("t-new") == []


@pytest.mark.asyncio
async def test_deleting_a_thread_deletes_its_checkpoints() -> None:
    saver = InMemorySaver()
    await _run_turns(saver, "t-1")
    reader, graph = _patched(saver)
    with reader, graph:
        await thread_state.delete_thread_state("t-1")
        assert await thread_state.load_thread_messages("t-1") == []
