"""The agent hands its collector the document text exactly when edits are on.

`propose_edits` is a manifest flag; what the model actually sees is the tool
list built in `SimpleDeepAgent.ainvoke`. These tests run `ainvoke` against a
fake deep agent and inspect that list, so a regression in the wiring -- the
flag not reaching the reporter, or the document text not being read from the
backend files -- fails here rather than as a rejected edit in a live run.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepagents.backends.utils import create_file_data
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from lib.workflows.simple_deep_agent.agent import SimpleDeepAgent, _main_document_text
from lib.workflows.simple_deep_agent.agent_types import MAIN_DOCUMENT_PATH

_DOCUMENT = "# Title\n\nThe CBT protocol was applied."


def _context(files: dict[str, Any]) -> MagicMock:
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(
        return_value=files
    )
    return context


async def _tools_given_to_the_agent(agent: SimpleDeepAgent) -> list[BaseTool]:
    """Run `ainvoke` against a fake deep agent and return the tools it was built with."""
    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(
        return_value={"files": {}, "messages": [AIMessage(content="done")]}
    )
    # `llm` would build a real chat model (and its rate limiter) from the
    # context; the tool list is decided before the model matters.
    with (
        patch.object(SimpleDeepAgent, "llm", new=MagicMock()),
        patch(
            "lib.workflows.simple_deep_agent.agent.create_deep_agent",
            return_value=fake_agent,
        ) as create,
    ):
        await agent.ainvoke({})
    return create.call_args.kwargs["tools"]


def _report_issue(tools: list[BaseTool]) -> BaseTool:
    (tool,) = [tool for tool in tools if tool.name == "report_issue"]
    return tool


def test_main_document_text_reads_the_backend_file_or_none():
    assert _main_document_text({}) is None
    files = {MAIN_DOCUMENT_PATH: create_file_data(_DOCUMENT)}
    assert _main_document_text(files) == _DOCUMENT


@pytest.mark.asyncio
async def test_agent_with_edits_on_gives_the_model_the_edits_tool_checked_against_the_document():
    files = {MAIN_DOCUMENT_PATH: create_file_data(_DOCUMENT)}
    agent = SimpleDeepAgent(_context(files), user_prompt="x", propose_edits=True)

    tool = _report_issue(await _tools_given_to_the_agent(agent))

    assert tool.args_schema is not None
    assert "edits" in tool.args_schema.model_json_schema()["properties"]
    # The reporter got the real document: a verbatim quote from line 3 is
    # accepted, and one the document does not contain is rejected.
    issue = {
        "title": "t",
        "description": "d",
        "severity": "low",
        "start_line": 3,
        "end_line": 3,
    }
    accepted = tool.invoke(
        {
            **issue,
            "edits": [
                {
                    "original_text": "was applied",
                    "replacement_text": "was used",
                    "rationale": "r",
                }
            ],
        }
    )
    assert accepted.startswith("Recorded issue-1")
    rejected = tool.invoke(
        {
            **issue,
            "edits": [
                {
                    "original_text": "never there",
                    "replacement_text": "x",
                    "rationale": "r",
                }
            ],
        }
    )
    assert rejected.startswith("Issue was not recorded:")


@pytest.mark.asyncio
async def test_agent_with_edits_off_gives_the_model_the_plain_tool():
    files = {MAIN_DOCUMENT_PATH: create_file_data(_DOCUMENT)}
    agent = SimpleDeepAgent(_context(files), user_prompt="x")

    tool = _report_issue(await _tools_given_to_the_agent(agent))

    assert tool.args_schema is not None
    assert "edits" not in tool.args_schema.model_json_schema()["properties"]
    assert "edit" not in tool.description.lower()


@pytest.mark.asyncio
async def test_agent_with_edits_on_but_no_document_fails_loudly():
    # A backend without /main.md is a wiring error, not something to paper
    # over by silently recording issues without their edits.
    agent = SimpleDeepAgent(_context({}), user_prompt="x", propose_edits=True)

    with pytest.raises(ValueError, match="document text"):
        await _tools_given_to_the_agent(agent)


@pytest.mark.asyncio
async def test_agent_that_does_not_report_issues_gets_no_issue_tool():
    agent = SimpleDeepAgent(_context({}), user_prompt="x", report_issues=False)

    tools = await _tools_given_to_the_agent(agent)

    assert all(tool.name != "report_issue" for tool in tools)
