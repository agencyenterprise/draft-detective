"""Tests for the construction our deep agents share.

What they cover is what would break silently for every agent at once: the reasoning summary that makes
a wrong answer inspectable in Langfuse, the shared rate limiter, and the mounting of
the document and skills at the paths every skill's line numbers are defined against.
"""

from typing import Any
from unittest.mock import patch

from lib.agents.deep_agent_setup import (
    DEFAULT_MODEL,
    _with_our_additions,
    build_llm,
    build_skill_files,
    general_purpose_subagent,
    tool_names,
)


class TestModelConstruction:
    def test_reasoning_summary_is_requested(self) -> None:
        """The summary shows up in Langfuse, so a wrong answer can be inspected."""

        with patch("lib.agents.deep_agent_setup.init_chat_model") as init:
            build_llm(DEFAULT_MODEL, api_key="sk-test")

        kwargs = init.call_args.kwargs
        assert kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}
        assert kwargs["max_retries"] == 4
        assert kwargs["rate_limiter"] is not None, "share the project's rate limiter"
        assert "output_version" not in kwargs, "batch agents keep the default layout"

    def test_callers_can_pick_the_reasoning_and_the_content_layout(self) -> None:
        """What the chat agent needs: v1 blocks and a detailed summary for streaming."""

        with patch("lib.agents.deep_agent_setup.init_chat_model") as init:
            build_llm(
                DEFAULT_MODEL,
                api_key="sk-test",
                reasoning={"effort": "low", "summary": "detailed"},
                output_version="v1",
            )

        kwargs = init.call_args.kwargs
        assert kwargs["reasoning"] == {"effort": "low", "summary": "detailed"}
        assert kwargs["output_version"] == "v1"
        assert kwargs["api_key"] == "sk-test"


class TestAgentFiles:
    def test_skills_alone_mount_no_document(self) -> None:
        """What the Teams agent mounts: it opens its own document mid-run."""

        files = build_skill_files()
        assert "/main.md" not in files
        assert any(path.startswith("/skills/") for path in files)

    def test_mounted_skills_drop_the_web_search_consent_step(self) -> None:
        """Nobody is there to answer, and consent was settled before the run."""

        files = build_skill_files()
        mounted = str(files["/skills/reference-validation/SKILL.md"]["content"])
        assert "interactive-only" not in mounted
        assert "Do you consent" not in mounted
        assert "# Reference Validation" in mounted

    def test_interactive_agents_keep_the_consent_step_without_its_markers(self) -> None:
        """The chat has a user to ask, so the section applies; the markers are noise."""

        files = build_skill_files(interactive=True)
        mounted = str(files["/skills/reference-validation/SKILL.md"]["content"])
        assert "Do you consent" in mounted
        assert "interactive-only" not in mounted

    def test_skills_can_be_left_out_of_the_mount(self) -> None:
        files = build_skill_files(exclude={"literature-review"})
        assert not any(path.startswith("/skills/literature-review/") for path in files)
        assert "/skills/reference-validation/SKILL.md" in files


class TestToolNames:
    def test_names_are_deduplicated_and_sorted(self) -> None:
        class Message:
            def __init__(self, calls: list[dict[str, str]]) -> None:
                self.tool_calls = calls

        messages = [
            Message([{"name": "read_file"}, {"name": "grep"}]),
            Message([{"name": "read_file"}]),
        ]

        assert tool_names(list(messages)) == ["grep", "read_file"]

    def test_messages_without_tool_calls_are_ignored(self) -> None:
        assert tool_names([object(), object()]) == []


class TestBuildingADeepAgent:
    @staticmethod
    def _captured(**kwargs: Any) -> dict[str, Any]:
        seen: dict[str, Any] = {}

        def create(**received: Any) -> str:
            seen.update(received)
            return "graph"

        assert _with_our_additions(create)(**kwargs) == "graph"
        return seen

    def test_our_middleware_runs_ahead_of_the_callers(self) -> None:
        own = object()
        seen = self._captured(model="m", middleware=[own])
        assert [type(m).__name__ for m in seen["middleware"][:-1]] == [
            "TodoListMiddleware",
            "ReadFileLineNumbersMiddleware",
        ]
        assert seen["middleware"][-1] is own

    def test_the_general_purpose_subagent_runs_our_middleware_and_the_parents_skills(self) -> None:
        (subagent,) = self._captured(model="m", skills=["/skills/"])["subagents"]
        assert subagent["name"] == "general-purpose"
        assert subagent["skills"] == ["/skills/"]
        assert [type(m).__name__ for m in subagent["middleware"]] == [
            "TodoListMiddleware",
            "ReadFileLineNumbersMiddleware",
        ]

    def test_a_callers_own_general_purpose_subagent_is_kept(self) -> None:
        own = {"name": "general-purpose", "description": "mine", "system_prompt": "mine"}
        (subagent,) = self._captured(model="m", subagents=[own])["subagents"]
        assert {k: v for k, v in subagent.items() if k != "middleware"} == own

    def test_a_declared_subagent_runs_our_middleware_ahead_of_its_own(self) -> None:
        own = object()
        spec = {"name": "checker", "description": "d", "system_prompt": "p", "middleware": [own]}
        declared, _general_purpose = self._captured(model="m", subagents=[spec])["subagents"]
        assert [type(m).__name__ for m in declared["middleware"][:-1]] == [
            "TodoListMiddleware",
            "ReadFileLineNumbersMiddleware",
        ]
        assert declared["middleware"][-1] is own

    def test_middleware_a_subagent_already_runs_is_not_added_twice(self) -> None:
        spec = general_purpose_subagent()
        (subagent,) = self._captured(model="m", subagents=[spec])["subagents"]
        assert [type(m).__name__ for m in subagent["middleware"]] == [
            "TodoListMiddleware",
            "ReadFileLineNumbersMiddleware",
        ]

    def test_a_precompiled_subagent_is_used_as_given(self) -> None:
        compiled = {"name": "compiled", "description": "d", "runnable": object()}
        declared, _general_purpose = self._captured(model="m", subagents=[compiled])["subagents"]
        assert declared is compiled
