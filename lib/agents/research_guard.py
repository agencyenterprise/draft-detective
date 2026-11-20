"""Code-enforced limits on a live report's researchers, which read the open web.

The skill asks the agent to wait for the user's consent before any web search and
each researcher to write only its own note. Prompts alone can be talked out of
both: by instructions in the uploaded report, or in a page a researcher reads. This
middleware wraps the orchestrator's ``task`` tool so neither rests on the model:

- No researcher starts until a message from the user consents to web search. The
  page's plan-approval button sends that consent; the call is refused before it.
- Of the files a researcher hands back, only notes under the research folder whose
  file the task named are kept: one researcher can't rewrite a sibling's note or
  an approved file.
"""

import dataclasses
import re
from collections.abc import Awaitable, Callable, Mapping
from pathlib import PurePosixPath
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

from lib.agents.subagent_files import TASK_TOOL, ToolResult

RESEARCHER = "researcher"

# The user's consent, as the page's plan-approval button words it. An affirmation,
# so a refusal ("I do not consent to running web search") doesn't pass.
CONSENT = "yes, i consent to running web search"

NO_CONSENT = (
    "Not started: research needs the user's consent to web search, and none was "
    "given in this conversation. Ask the user to approve the research plan, which "
    "gives it, and start the research after that."
)


def _consented(state: Mapping[str, Any] | None) -> bool:
    messages = (state or {}).get("messages") or []
    return any(
        isinstance(m, HumanMessage) and CONSENT in m.text.lower() for m in messages
    )


def _is_research_task(request: ToolCallRequest) -> bool:
    call = request.tool_call
    return call["name"] == TASK_TOOL and call["args"].get("subagent_type") == RESEARCHER


def only_assigned_notes(
    request: ToolCallRequest, result: ToolResult, research_dir: str
) -> ToolResult:
    """A researcher's result, keeping only the notes its task named (by file name,
    so a task that gives the path relative to the report's folder still counts)."""

    if not isinstance(result, Command) or not isinstance(result.update, Mapping):
        return result
    files = result.update.get("files")
    if not files:
        return result
    named = str(request.tool_call["args"].get("description") or "")
    kept = {
        path: data
        for path, data in files.items()
        if path.startswith(f"{research_dir}/")
        and _names(named, PurePosixPath(path).name)
    }
    return dataclasses.replace(result, update={**result.update, "files": kept})


def _names(text: str, file_name: str) -> bool:
    """Whether ``text`` names the file as a whole: ``F1.md``, not inside ``AF1.md``."""

    return re.search(rf"(?<![\w-]){re.escape(file_name)}", text) is not None


def _refused(request: ToolCallRequest) -> ToolMessage:
    return ToolMessage(
        content=NO_CONSENT,
        tool_call_id=request.tool_call["id"],
        name=TASK_TOOL,
        status="error",
    )


class ResearchGuardMiddleware(AgentMiddleware[Any, Any, Any]):
    """Holds researchers to the user's consent and to their own notes."""

    def __init__(self, research_dir: str) -> None:
        super().__init__()
        self.research_dir = research_dir.rstrip("/")

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolResult],
    ) -> ToolResult:
        if not _is_research_task(request):
            return handler(request)
        if not _consented(request.state):
            return _refused(request)
        return only_assigned_notes(request, handler(request), self.research_dir)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolResult]],
    ) -> ToolResult:
        if not _is_research_task(request):
            return await handler(request)
        if not _consented(request.state):
            return _refused(request)
        return only_assigned_notes(request, await handler(request), self.research_dir)
