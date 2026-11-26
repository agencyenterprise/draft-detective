"""A subagent hands back only the files it changed, so parallel subagents can't clobber.

deepagents returns a subagent's whole final state to its parent, ``files`` included:
every file the subagent inherited comes back with it, and the parent's files reducer
lets the later update win for each path. When several subagents run in parallel,
each one's copy of the filesystem dates from when it started, so one that finishes
later writes its stale copy of a sibling's file over what the sibling just wrote.
A live report's research redone in parallel lost every rewritten note this way.

This middleware wraps the ``task`` tool on the parent: of the files a subagent hands
back, it keeps those that differ from the parent's filesystem at the time of the call.
Parallel calls all start from the same snapshot, so what a subagent didn't touch is
dropped, and the files it wrote or deleted pass through. It also keeps each
subagent from writing the whole mounted filesystem back into the checkpoint.
"""

import dataclasses
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

TASK_TOOL = "task"

ToolResult = ToolMessage | Command[Any]


def changed_files(
    held: Mapping[str, Any], returned: Mapping[str, Any]
) -> dict[str, Any]:
    """The returned files that differ from what was held; a deletion always counts."""

    return {
        path: data
        for path, data in returned.items()
        if data is None or held.get(path) != data
    }


def only_changed_files(request: ToolCallRequest, result: ToolResult) -> ToolResult:
    """A ``task`` result with its files narrowed to what the subagent changed."""

    if request.tool_call["name"] != TASK_TOOL or not isinstance(result, Command):
        return result
    update = result.update
    if not isinstance(update, Mapping) or "files" not in update:
        return result
    held = (request.state or {}).get("files") or {}
    narrowed = {**update, "files": changed_files(held, update["files"] or {})}
    return dataclasses.replace(result, update=narrowed)


class SubagentFileChangesMiddleware(AgentMiddleware[Any, Any, Any]):
    """Narrows each subagent's returned files to the ones it changed."""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolResult],
    ) -> ToolResult:
        return only_changed_files(request, handler(request))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolResult]],
    ) -> ToolResult:
        return only_changed_files(request, await handler(request))
