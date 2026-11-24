"""A subagent's returned files are narrowed to what it changed.

The failure it prevents: two subagents run in parallel from the same snapshot; one
rewrites a note, the other hands back its untouched (now stale) copy, and whichever
update the parent applies last decides what the note says.
"""

import asyncio
import itertools
from typing import Any

import pytest
from deepagents.backends.utils import create_file_data, file_data_to_string
from deepagents.middleware.filesystem import _file_data_reducer
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from lib.agents.deep_agent_setup import agent_input, build_deep_agent
from lib.agents.subagent_files import (
    SubagentFileChangesMiddleware,
    changed_files,
    only_changed_files,
)

OLD = create_file_data("old notes")
NEW = create_file_data("new notes")
SKILL = create_file_data("skill")
HELD = {"/notes/C4.md": OLD, "/skills/x/SKILL.md": SKILL}


def _request(
    name: str = "task", files: dict[str, Any] | None = None
) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={"name": name, "args": {}, "id": "call-1"},
        tool=None,
        state={"files": HELD if files is None else files},
        runtime=None,  # type: ignore[arg-type]
    )


def _task_result(files: dict[str, Any]) -> Command[Any]:
    return Command(
        update={
            "files": files,
            "messages": [ToolMessage("done", tool_call_id="call-1")],
        }
    )


def test_only_what_the_subagent_changed_or_deleted_passes() -> None:
    returned = {
        "/notes/C4.md": NEW,
        "/skills/x/SKILL.md": SKILL,
        "/notes/A1.md": NEW,
        "/notes/gone.md": None,
    }
    assert changed_files(HELD, returned) == {
        "/notes/C4.md": NEW,
        "/notes/A1.md": NEW,
        "/notes/gone.md": None,
    }


@pytest.mark.parametrize("order", list(itertools.permutations([0, 1])))
def test_parallel_subagents_no_longer_clobber_each_other(
    order: tuple[int, ...],
) -> None:
    rewrote = only_changed_files(
        _request(), _task_result({**HELD, "/notes/C4.md": NEW})
    )
    untouched = only_changed_files(_request(), _task_result(dict(HELD)))
    updates = [rewrote, untouched]

    files = dict(HELD)
    for i in order:
        update = updates[i]
        assert isinstance(update, Command) and isinstance(update.update, dict)
        files = _file_data_reducer(files, update.update["files"])

    assert files["/notes/C4.md"] == NEW


def test_the_rest_of_the_update_is_kept() -> None:
    result = only_changed_files(_request(), _task_result({**HELD, "/notes/C4.md": NEW}))
    assert isinstance(result, Command) and isinstance(result.update, dict)
    assert result.update["files"] == {"/notes/C4.md": NEW}
    assert result.update["messages"][0].content == "done"


def test_other_tools_and_plain_messages_are_untouched() -> None:
    command = _task_result(dict(HELD))
    assert only_changed_files(_request(name="write_file"), command) is command
    message = ToolMessage("text", tool_call_id="call-1")
    assert only_changed_files(_request(), message) is message


@pytest.mark.asyncio
async def test_the_middleware_wraps_sync_and_async_calls() -> None:
    middleware = SubagentFileChangesMiddleware()
    result = _task_result(dict(HELD))

    async def ahandler(_request: ToolCallRequest) -> Command[Any]:
        return result

    for narrowed in (
        middleware.wrap_tool_call(_request(), lambda _r: result),
        await middleware.awrap_tool_call(_request(), ahandler),
    ):
        assert isinstance(narrowed, Command) and isinstance(narrowed.update, dict)
        assert narrowed.update["files"] == {}


@pytest.mark.asyncio
async def test_in_a_real_graph_a_stale_sibling_cannot_undo_a_rewrite() -> None:
    """Two subagents in parallel over a delta-channel filesystem: the parent ends up
    with the rewrite, whichever order they finish in (the stale one is made last)."""

    class FakeModel(GenericFakeChatModel):
        def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeModel":
            return self

    async def rewriter(state: dict[str, Any]) -> dict[str, Any]:
        files = {**state["files"], "/notes/C4.md": NEW}
        return {"messages": [AIMessage("rewrote C4")], "files": files}

    async def stale(state: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.05)  # finish after the rewriter
        return {"messages": [AIMessage("nothing to do")], "files": dict(state["files"])}

    calls = [
        {"name": "task", "args": {"description": d, "subagent_type": t}, "id": f"c{i}"}
        for i, (d, t) in enumerate([("C4", "rewriter"), ("A1", "stale")])
    ]
    model = FakeModel(
        messages=iter([AIMessage(content="", tool_calls=calls), AIMessage("done")])
    )
    agent = build_deep_agent(
        model=model,
        subagents=[
            {
                "name": "rewriter",
                "description": "r",
                "runnable": RunnableLambda(rewriter),
            },
            {"name": "stale", "description": "s", "runnable": RunnableLambda(stale)},
        ],
        checkpointer=InMemorySaver(),
    )
    config: RunnableConfig = {"configurable": {"thread_id": "t"}}
    await agent.ainvoke(
        agent_input(files={"/notes/C4.md": OLD}, messages=[HumanMessage("go")]),
        config=config,
    )
    state = await agent.aget_state(config)
    assert file_data_to_string(state.values["files"]["/notes/C4.md"]) == "new notes"
