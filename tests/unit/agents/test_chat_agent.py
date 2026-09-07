"""The chat agent's construction and catalogues.

Pins the settings the streaming experiments settled on (``output_version="v1"``,
a ``detailed`` reasoning summary, hosted web search, skills mounted with their
interactive sections), the model allowlist fallback, and that every skill in the
slash-command map points at a real skill and a registered workflow.
"""

from pathlib import Path
from unittest.mock import patch

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
)
from lib.agents.deep_agent_setup import RECURSION_LIMIT, SKILLS_DIR
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
    def test_the_agent_is_built_with_the_streaming_settings(self) -> None:
        llm = object()
        with (
            patch.object(chat_agent, "build_llm", return_value=llm) as build_llm,
            patch.object(chat_agent, "create_deep_agent", return_value="graph") as create,
        ):
            assert build_chat_agent(resolve_chat_model("gpt-5.6-sol"), "sk-user") == "graph"

        model, api_key = build_llm.call_args.args
        assert model.name == "gpt-5.6-sol" and api_key == "sk-user"
        assert build_llm.call_args.kwargs == {"reasoning": CHAT_REASONING, "output_version": "v1"}
        assert CHAT_REASONING["summary"] == "detailed"

        kwargs = create.call_args.kwargs
        assert kwargs["model"] is llm
        assert kwargs["tools"] == [{"type": "web_search"}]
        assert kwargs["skills"] == ["/skills/"]
        assert kwargs["system_prompt"].startswith("You are Draft Detective")
        assert "checkpointer" not in kwargs

    def test_the_input_mounts_interactive_skills_and_the_conversation(self) -> None:
        agent_input = build_chat_input([HumanMessage(content="hi")])

        assert [m.content for m in agent_input["messages"]] == ["hi"]
        files = agent_input["files"]
        assert "/skills/voice-and-tone/SKILL.md" in files
        for excluded in EXCLUDED_CHAT_SKILLS:
            assert not any(path.startswith(f"/skills/{excluded}/") for path in files)
        # The consent step stays (there is a user to ask); only its markers go.
        validation = str(files["/skills/reference-validation/SKILL.md"]["content"])
        assert "consent" in validation.lower()
        assert INTERACTIVE_ONLY_START not in validation

    def test_the_run_is_traced_per_thread(self) -> None:
        config = chat_run_config(thread_id="t-1", user_id="u-1")
        assert config["recursion_limit"] == RECURSION_LIMIT
        assert config["metadata"]["langfuse_session_id"] == "t-1"
        assert config["metadata"]["langfuse_user_id"] == "u-1"
        assert "chat" in config["metadata"]["langfuse_tags"]


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
