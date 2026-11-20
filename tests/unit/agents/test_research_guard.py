"""Researchers start only after the user's consent, and keep only their own note."""

from typing import Any

import pytest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from lib.agents.research_guard import NO_CONSENT, ResearchGuardMiddleware

GUARD = ResearchGuardMiddleware("/live-report/research")
CONSENT = HumanMessage(
    "The plan is approved. Yes, I consent to running web search on this document."
)


def _request(messages: list[Any], subagent: str = "researcher") -> ToolCallRequest:
    call = {
        "name": "task",
        "id": "call-1",
        "args": {
            "subagent_type": subagent,
            "description": "Research F1. Write your notes to /live-report/research/F1.md.",
        },
    }
    return ToolCallRequest(
        tool_call=call,  # type: ignore[arg-type]
        tool=None,
        state={"messages": messages, "files": {}},
        runtime=None,  # type: ignore[arg-type]
    )


def _returning(files: dict[str, Any]) -> Any:
    calls: list[ToolCallRequest] = []

    def handler(request: ToolCallRequest) -> Command:
        calls.append(request)
        return Command(update={"files": files, "messages": []})

    return handler, calls


def test_no_researcher_starts_before_the_user_consents() -> None:
    handler, calls = _returning({})
    result = GUARD.wrap_tool_call(_request([HumanMessage("Check F1 online.")]), handler)

    assert calls == []
    assert isinstance(result, ToolMessage)
    assert result.content == NO_CONSENT


def test_a_researcher_keeps_only_the_note_its_task_named() -> None:
    files = {
        "/live-report/research/F1.md": "mine",
        "/live-report/research/F11.md": "a sibling's",
        "/live-report/research/F2.md": "a sibling's",
        "/live-report/research-plan.md": "the approved plan",
    }
    handler, calls = _returning(files)
    result = GUARD.wrap_tool_call(_request([CONSENT, AIMessage("Starting.")]), handler)

    assert len(calls) == 1
    assert isinstance(result, Command)
    assert isinstance(result.update, dict)
    assert result.update["files"] == {"/live-report/research/F1.md": "mine"}


def test_other_subagents_pass_through() -> None:
    files = {"/live-report/research-brief.md": "brief"}
    handler, _ = _returning(files)
    result = GUARD.wrap_tool_call(
        _request([HumanMessage("go")], subagent="synthesizer"), handler
    )

    assert isinstance(result, Command)
    assert isinstance(result.update, dict)
    assert result.update["files"] == files


@pytest.mark.asyncio
async def test_the_async_path_holds_the_same_rules() -> None:
    async def handler(request: ToolCallRequest) -> Command:
        raise AssertionError("must not run")

    result = await GUARD.awrap_tool_call(_request([HumanMessage("hi")]), handler)
    assert isinstance(result, ToolMessage)
