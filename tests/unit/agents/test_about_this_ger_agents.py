"""Tests for the About This (GER) validator agents.

These agents load their rules from a portable skill (the source of truth) and
append a backend `_ENV_GUIDANCE` addendum carrying the Draft-Detective specifics
the skill omits (document location, issues output contract). Here we guard that
the skill loads and the addendum still references those specifics, without
invoking the LLM.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from lib.agents.authors_validator import _ENV_GUIDANCE as AUTHORS_ENV_GUIDANCE
from lib.agents.authors_validator import AuthorsValidatorAgent
from lib.agents.preface_validator import _ENV_GUIDANCE as PREFACE_ENV_GUIDANCE
from lib.agents.preface_validator import PrefaceValidatorAgent
from lib.skills import load_skill_prompt
from lib.workflows.simple_deep_agent.agent_types import MARKDOWN_REPORT_PATH

CONVERSATION = AIMessage(content="done")

_CASES = [
    ("about-this-preface", PREFACE_ENV_GUIDANCE),
    ("about-this-authors", AUTHORS_ENV_GUIDANCE),
]


@pytest.mark.parametrize("skill, env_guidance", _CASES)
def test_agent_composes_skill_with_env_guidance(skill: str, env_guidance: str):
    body = load_skill_prompt(skill)
    assert body.strip()

    # The backend addendum carries the specifics the portable skill omits.
    assert "/main.md" in env_guidance
    assert "/skills/issues/SKILL.md" in env_guidance
    assert MARKDOWN_REPORT_PATH in env_guidance
    assert "write_file" in env_guidance
    assert "report_issue" in env_guidance

    composed = body + env_guidance
    assert composed.startswith(body)
    assert composed.endswith(env_guidance)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type, create_agent_path",
    [
        (
            PrefaceValidatorAgent,
            "lib.agents.preface_validator.create_deep_agent",
        ),
        (
            AuthorsValidatorAgent,
            "lib.agents.authors_validator.create_deep_agent",
        ),
    ],
)
async def test_agent_delivers_issues_by_tool_and_report_by_file(
    agent_type: type, create_agent_path: str
):
    context = MagicMock()
    context.file_artifacts_service.get_deepagent_backend_files = AsyncMock(
        return_value={}
    )
    agent = agent_type(context)
    agent._llm = MagicMock()

    async def invoke_agent(_input: dict, config: dict) -> dict:
        tools = {
            tool.name: tool
            for tool in create_agent.call_args.kwargs["tools"]
            if hasattr(tool, "name")
        }
        tools["report_issue"].invoke(
            {
                "title": "Missing section",
                "description": "The section was not found.",
                "severity": "medium",
                "start_line": 1,
                "end_line": 1,
            }
        )
        return {
            "messages": [CONVERSATION],
            "files": {MARKDOWN_REPORT_PATH: {"content": ["# Report", "One issue."]}},
        }

    with patch(create_agent_path) as create_agent:
        create_agent.return_value.ainvoke = AsyncMock(side_effect=invoke_agent)
        result, messages = await agent.ainvoke({})

    assert "response_format" not in create_agent.call_args.kwargs
    assert result.report_markdown == "# Report\nOne issue."
    assert [issue.title for issue in result.issues] == ["Missing section"]
    # The conversation comes back so the workflow can persist it.
    assert messages == [CONVERSATION]
