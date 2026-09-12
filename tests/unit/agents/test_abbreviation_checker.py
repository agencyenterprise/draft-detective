"""Tests for the abbreviation checker agent.

The agent loads its extraction method from the portable `abbreviation-extraction`
skill (the source of truth) and appends a backend `_ENV_GUIDANCE` addendum
carrying the Draft-Detective specifics the skill omits (document location and the
structured-output field mapping the downstream deterministic checks depend on).
Here we guard that the skill loads and the addendum still references those
specifics, without invoking the LLM.
"""

import pytest

from lib.agents.abbreviation_checker import (
    _ENV_GUIDANCE,
    AbbreviationCheckerAgent,
)
from lib.skills import load_skill_prompt
from lib.workflows.abbreviation_scan_v2.state import AbbreviationCheckOutput
from lib.workflows.simple_deep_agent.agent_types import DEEP_AGENT_RECURSION_LIMIT


class _StubContext:
    """Minimal stand-in for ContextSchema: the agent only reads files from it."""

    openai_api_key = None

    class _Files:
        async def get_deepagent_backend_files(self) -> dict:
            return {}

    file_artifacts_service = _Files()


def test_extraction_skill_loads_non_empty_without_frontmatter():
    body = load_skill_prompt("abbreviation-extraction")
    assert body.strip()
    assert not body.lstrip().startswith("---")


def test_agent_composes_skill_with_env_guidance():
    body = load_skill_prompt("abbreviation-extraction")

    # The backend addendum carries the specifics the portable skill omits:
    # document location and the exact structured-output field mapping.
    assert "/main.md" in _ENV_GUIDANCE
    for field in (
        "inline_definition",
        "occurrence_number",
        "line_start",
        "line_end",
        "abbreviations_section_definition",
        "ignored",
        "abbreviations_section_found",
    ):
        assert field in _ENV_GUIDANCE

    composed = body + _ENV_GUIDANCE
    assert composed.startswith(body)
    assert composed.endswith(_ENV_GUIDANCE)


def test_env_guidance_directs_the_catalogue_to_the_tool():
    """The catalogue must not go back through the terminal response."""
    assert "record_abbreviations" in _ENV_GUIDANCE
    assert "200" in _ENV_GUIDANCE  # chunk size and per-call batch cap


class TestCollectorWiring:
    """The agent must hand the collector's tool to the deep agent and return
    what the collector gathered.

    Covered here rather than in the reporter's own tests: those invoke the tool
    directly, so a regression in `tools=reporter.tools` or in returning
    `reporter.occurrences` would slip through as an empty catalogue and no
    issues, which is exactly the silent failure this workflow already had once.
    """

    @pytest.mark.asyncio
    async def test_tool_is_supplied_and_recorded_occurrences_are_returned(
        self, monkeypatch
    ):
        captured: dict = {}

        def fake_create_deep_agent(**kwargs):
            captured.update(kwargs)

            class _Agent:
                async def ainvoke(self, payload, config=None):
                    # Stand in for the model: call the collector's tool the way
                    # the real agent is instructed to.
                    tool = captured["tools"][0]
                    tool.invoke(
                        {
                            "occurrences": [
                                {
                                    "abbr": "NATO",
                                    "inline_definition": "",
                                    "occurrence_number": 1,
                                    "line_start": 12,
                                    "line_end": 12,
                                    "abbreviations_section_definition": None,
                                    "ignored": False,
                                    "ignored_reason": None,
                                }
                            ]
                        }
                    )
                    return {
                        "structured_response": AbbreviationCheckOutput(
                            abbreviations_section_found=True, reasoning="done"
                        ),
                        "messages": [],
                    }

            return _Agent()

        monkeypatch.setattr(
            "lib.agents.abbreviation_checker.create_deep_agent", fake_create_deep_agent
        )

        agent = AbbreviationCheckerAgent(_StubContext())
        monkeypatch.setattr(
            type(agent), "llm", property(lambda self: object()), raising=False
        )

        output, occurrences, _messages = await agent.ainvoke({})

        assert captured.get("tools"), "the collector's tool was not passed to the agent"
        assert captured["tools"][0].name == "record_abbreviations"
        assert [o.abbr for o in occurrences] == ["NATO"]
        assert occurrences[0].line_start == 12
        assert output.abbreviations_section_found is True

    @pytest.mark.asyncio
    async def test_returns_empty_catalogue_when_the_tool_is_never_called(
        self, monkeypatch
    ):
        def fake_create_deep_agent(**kwargs):
            class _Agent:
                async def ainvoke(self, payload, config=None):
                    return {
                        "structured_response": AbbreviationCheckOutput(
                            abbreviations_section_found=False, reasoning="nothing found"
                        ),
                        "messages": [],
                    }

            return _Agent()

        monkeypatch.setattr(
            "lib.agents.abbreviation_checker.create_deep_agent", fake_create_deep_agent
        )
        agent = AbbreviationCheckerAgent(_StubContext())
        monkeypatch.setattr(
            type(agent), "llm", property(lambda self: object()), raising=False
        )

        _output, occurrences, _messages = await agent.ainvoke({})
        assert occurrences == []


@pytest.mark.asyncio
async def test_recursion_limit_scales_with_the_shared_budget(monkeypatch):
    """A fixed budget would cap how long a document the agent can finish."""
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        class _Agent:
            async def ainvoke(self, payload, config=None):
                captured["config"] = config
                return {
                    "structured_response": AbbreviationCheckOutput(
                        abbreviations_section_found=False, reasoning=""
                    ),
                    "messages": [],
                }

        return _Agent()

    monkeypatch.setattr(
        "lib.agents.abbreviation_checker.create_deep_agent", fake_create_deep_agent
    )
    agent = AbbreviationCheckerAgent(_StubContext())
    monkeypatch.setattr(
        type(agent), "llm", property(lambda self: object()), raising=False
    )

    await agent.ainvoke({})
    assert captured["config"]["recursion_limit"] == DEEP_AGENT_RECURSION_LIMIT
