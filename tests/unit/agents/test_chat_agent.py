"""The chat agent's construction and catalogues.

Pins the settings the streaming experiments settled on (``output_version="v1"``,
a ``detailed`` reasoning summary, hosted web search, skills mounted with their
interactive sections), that the thread is checkpointed under the chat thread id,
the model allowlist fallback, and that every skill in the slash-command map
points at a real skill and a registered workflow.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from lib.agents import chat_agent
from lib.agents.chat_agent import (
    CHAT_MODELS,
    CHAT_REASONING,
    DEFAULT_CHAT_MODEL,
    EXCLUDED_CHAT_SKILLS,
    SKILL_WORKFLOWS,
    build_chat_agent,
    build_chat_input,
    chat_run_config,
    chat_skill_catalogue,
    resolve_chat_model,
    run_chat_turn,
)
from lib.agents.deep_agent_setup import RECURSION_LIMIT, SKILLS_DIR
from lib.services.chat.history import ChatAttachment
from lib.skills import INTERACTIVE_ONLY_START
from lib.workflows.registry import get_all_manifests


class TestResolveChatModel:
    def test_known_ids_resolve_and_anything_else_is_the_default(self) -> None:
        assert resolve_chat_model("gpt-5.6-luna").name == "gpt-5.6-luna"
        assert resolve_chat_model("gpt-4.1") == DEFAULT_CHAT_MODEL
        assert resolve_chat_model(None) == DEFAULT_CHAT_MODEL
        assert resolve_chat_model("") == DEFAULT_CHAT_MODEL

    def test_ids_are_unique(self) -> None:
        ids = [option.id for option in CHAT_MODELS]
        assert len(ids) == len(set(ids))


class TestBuildChatAgent:
    def test_the_agent_is_built_with_the_streaming_settings_and_the_checkpointer(self) -> None:
        llm, saver = object(), object()
        with (
            patch.object(chat_agent, "build_llm", return_value=llm) as build_llm,
            patch.object(chat_agent, "create_deep_agent", return_value="graph") as create,
        ):
            assert build_chat_agent(resolve_chat_model("gpt-5.6-sol"), "sk-user", saver) == "graph"  # type: ignore[arg-type]

        model, api_key = build_llm.call_args.args
        assert model.name == "gpt-5.6-sol" and api_key == "sk-user"
        assert build_llm.call_args.kwargs == {"reasoning": CHAT_REASONING, "output_version": "v1"}
        assert CHAT_REASONING["summary"] == "detailed"

        kwargs = create.call_args.kwargs
        assert kwargs["model"] is llm
        assert kwargs["checkpointer"] is saver
        assert kwargs["tools"] == [{"type": "web_search"}]
        assert kwargs["skills"] == ["/skills/"]
        assert kwargs["system_prompt"].startswith("You are Draft Detective")

    def test_the_input_mounts_interactive_skills_plus_the_turn_files(self) -> None:
        message = HumanMessage(content="hi")
        agent_input = build_chat_input(message, {"/attachments/a.md": {"content": ["x"]}})

        assert agent_input["messages"] == [message]
        files = agent_input["files"]
        assert files["/attachments/a.md"] == {"content": ["x"]}
        assert "/skills/voice-and-tone/SKILL.md" in files
        for excluded in EXCLUDED_CHAT_SKILLS:
            assert not any(path.startswith(f"/skills/{excluded}/") for path in files)
        # The consent step stays (there is a user to ask); only its markers go.
        validation = str(files["/skills/reference-validation/SKILL.md"]["content"])
        assert "consent" in validation.lower()
        assert INTERACTIVE_ONLY_START not in validation

    def test_the_run_is_keyed_and_traced_per_thread(self) -> None:
        config = chat_run_config(thread_id="t-1", user_id="u-1")
        assert config["configurable"] == {"thread_id": "t-1"}
        assert config["recursion_limit"] == RECURSION_LIMIT
        assert config["metadata"]["langfuse_session_id"] == "t-1"
        assert config["metadata"]["langfuse_user_id"] == "u-1"
        assert "chat" in config["metadata"]["langfuse_tags"]


class TestRunChatTurn:
    async def _collect(self, events: AsyncIterator[Any]) -> list[Any]:
        return [event async for event in events]

    @pytest.mark.asyncio
    async def test_a_turn_borrows_a_saver_and_streams_the_agent(self) -> None:
        saver = object()
        seen: dict[str, Any] = {}

        @asynccontextmanager
        async def get_checkpointer():
            yield saver

        async def fake_stream(agent: Any, agent_input: Any, config: Any) -> AsyncIterator[dict]:
            seen.update(agent=agent, agent_input=agent_input, config=config)
            yield {"t": "text", "v": "ok"}

        with (
            patch.object(chat_agent, "get_checkpointer", get_checkpointer),
            patch.object(chat_agent, "build_chat_agent", return_value="graph") as build,
            patch.object(chat_agent, "stream_chat_events", fake_stream),
        ):
            events = await self._collect(
                run_chat_turn(
                    thread_id="t-1",
                    user_id="u-1",
                    model=DEFAULT_CHAT_MODEL,
                    api_key=None,
                    text="Read this.",
                    attachments=[ChatAttachment(name="draft.pdf", text="body")],
                    message_id="page-id-1",
                )
            )

        assert events == [{"t": "text", "v": "ok"}]
        assert build.call_args.args == (DEFAULT_CHAT_MODEL, None, saver)
        assert seen["agent"] == "graph"
        assert seen["config"]["configurable"] == {"thread_id": "t-1"}
        (message,) = seen["agent_input"]["messages"]
        assert message.id == "page-id-1"
        assert message.additional_kwargs["user_text"] == "Read this."
        assert "/attachments/draft.md" in seen["agent_input"]["files"]
        assert "/skills/voice-and-tone/SKILL.md" in seen["agent_input"]["files"]


class TestSkillCatalogue:
    def test_every_mapped_skill_exists_and_has_a_registered_workflow(self) -> None:
        manifests = get_all_manifests()
        for skill, workflow_type in SKILL_WORKFLOWS.items():
            assert (SKILLS_DIR / skill / "SKILL.md").is_file(), skill
            assert workflow_type in manifests, skill

    def test_descriptions_come_from_the_manifest_when_there_is_one(self) -> None:
        manifests = get_all_manifests()
        by_name = {skill.name: skill.description for skill in chat_skill_catalogue()}

        assert by_name["reviewer-2"] == manifests[SKILL_WORKFLOWS["reviewer-2"]].description
        # A helper skill without a workflow keeps its own description.
        assert "voice-and-tone" in by_name
        assert by_name["voice-and-tone"].startswith("How Draft Detective writes")
        assert set(by_name).isdisjoint(EXCLUDED_CHAT_SKILLS)

    def test_a_retired_workflow_falls_back_to_the_skill_description(self) -> None:
        with patch.object(chat_agent, "get_all_manifests", return_value={}):
            by_name = {skill.name: skill.description for skill in chat_skill_catalogue()}
        own = (SKILLS_DIR / "reviewer-2" / "SKILL.md").read_text()
        assert by_name["reviewer-2"]
        assert by_name["reviewer-2"][:40] in own.replace("\n  ", " ").replace("\n", " ")

    def test_excluded_skills_exist_on_disk(self) -> None:
        """The exclusion list names real skills; a typo would silently exclude nothing."""
        for skill in EXCLUDED_CHAT_SKILLS:
            assert Path(SKILLS_DIR / skill / "SKILL.md").is_file(), skill
