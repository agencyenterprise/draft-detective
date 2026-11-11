"""Tests for the construction our deep agents share.

What they cover is what would break silently for every agent at once: the reasoning summary that makes
a wrong answer inspectable in Langfuse, the shared rate limiter, and the run config that
keys a conversation's checkpoint and its Langfuse session by one id. Mounting the skills
is covered with the rest of ``lib/skills.py`` in ``tests/unit/test_skills.py``.
"""

from typing import Any
from unittest.mock import patch

from lib.agents.deep_agent_setup import (
    DEFAULT_MODEL,
    RECURSION_LIMIT,
    _with_our_additions,
    build_llm,
    conversation_run_config,
    general_purpose_subagent,
)
from lib.config.langfuse import langfuse_handler
from lib.config.llm_error_logger import ErrorLoggingCallback


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


class TestConversationRunConfig:
    def test_one_id_keys_the_checkpoint_and_the_langfuse_session(self) -> None:
        config = conversation_run_config("t-1", run_name="agent", tags=["a", "b"])
        assert config["configurable"] == {"thread_id": "t-1"}
        assert config["run_name"] == "agent"
        assert config["recursion_limit"] == RECURSION_LIMIT
        assert config["metadata"] == {
            "langfuse_tags": ["a", "b"],
            "langfuse_session_id": "t-1",
        }

    def test_traces_go_to_langfuse_and_errors_are_logged(self) -> None:
        callbacks = conversation_run_config("t-1", run_name="agent", tags=[])[
            "callbacks"
        ]
        assert isinstance(callbacks, list)
        assert callbacks[0] is langfuse_handler
        assert isinstance(callbacks[1], ErrorLoggingCallback)

    def test_extra_fields_cannot_replace_the_reserved_ones(self) -> None:
        config = conversation_run_config(
            "t-1",
            run_name="agent",
            tags=["a"],
            metadata={"langfuse_tags": "x", "langfuse_session_id": "other"},
        )
        assert config["metadata"]["langfuse_tags"] == ["a"]
        assert config["metadata"]["langfuse_session_id"] == "t-1"

    def test_the_user_and_extra_fields_join_the_trace(self) -> None:
        config = conversation_run_config(
            "t-1",
            run_name="agent",
            tags=["a"],
            user_id="u-1",
            metadata={"links_found": "2"},
        )
        assert config["metadata"] == {
            "langfuse_tags": ["a"],
            "links_found": "2",
            "langfuse_session_id": "t-1",
            "langfuse_user_id": "u-1",
        }


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

    def test_the_general_purpose_subagent_runs_our_middleware_and_the_parents_skills(
        self,
    ) -> None:
        (subagent,) = self._captured(model="m", skills=["/skills/"])["subagents"]
        assert subagent["name"] == "general-purpose"
        assert subagent["skills"] == ["/skills/"]
        assert [type(m).__name__ for m in subagent["middleware"]] == [
            "TodoListMiddleware",
            "ReadFileLineNumbersMiddleware",
        ]

    def test_a_callers_own_general_purpose_subagent_is_kept(self) -> None:
        own = {
            "name": "general-purpose",
            "description": "mine",
            "system_prompt": "mine",
        }
        (subagent,) = self._captured(model="m", subagents=[own])["subagents"]
        assert {k: v for k, v in subagent.items() if k != "middleware"} == own

    def test_a_declared_subagent_runs_our_middleware_ahead_of_its_own(self) -> None:
        own = object()
        spec = {
            "name": "checker",
            "description": "d",
            "system_prompt": "p",
            "middleware": [own],
        }
        declared, _general_purpose = self._captured(model="m", subagents=[spec])[
            "subagents"
        ]
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
        declared, _general_purpose = self._captured(model="m", subagents=[compiled])[
            "subagents"
        ]
        assert declared is compiled
