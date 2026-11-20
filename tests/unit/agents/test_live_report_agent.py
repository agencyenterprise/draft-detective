"""The live-report orchestrator's construction, and how threads pick their agent.

Pins what keeps the orchestrator lean: no web search of its own, research and the
brief delegated to subagents (only the researcher searches), only this flow's
skills mounted, and every step file the prompts send the agents to on disk.
"""

import re
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from deepagents.middleware.filesystem import _check_fs_permission
from langchain_core.messages import HumanMessage

from lib.agents import chat_agent, live_report_agent
from lib.agents.chat_agent import CHAT_REASONING, resolve_chat_model
from lib.agents.live_report_agent import (
    LIVE_REPORT_SKILLS,
    RESEARCHER_PERMISSIONS,
    RESEARCHER_PROMPT,
    SYNTHESIZER_PERMISSIONS,
    SYNTHESIZER_PROMPT,
    SYSTEM_PROMPT,
    build_live_report_agent,
    build_live_report_input,
    live_report_run_config,
    researcher_prompt,
)
from lib.agents.thread_agents import thread_agent
from lib.models.chat_thread import ChatThreadKind
from lib.skills import _SKILLS_DIR, INTERACTIVE_ONLY_START


def _build() -> dict[str, Any]:
    with (
        patch.object(live_report_agent, "build_llm", return_value="llm") as build_llm,
        patch.object(
            live_report_agent, "build_deep_agent", return_value="graph"
        ) as create,
    ):
        graph = build_live_report_agent(
            resolve_chat_model("gpt-5.6-sol"),
            "sk-user",
            "saver",  # type: ignore[arg-type]
        )
    assert graph == "graph"
    assert build_llm.call_args.kwargs == {
        "reasoning": CHAT_REASONING,
        "output_version": "v1",
    }
    return dict(create.call_args.kwargs)


class TestBuild:
    def test_the_orchestrator_has_no_web_search_of_its_own(self) -> None:
        kwargs = _build()
        assert kwargs["tools"] == []
        assert kwargs["checkpointer"] == "saver"
        assert kwargs["system_prompt"] == SYSTEM_PROMPT

    def test_only_the_researcher_searches(self) -> None:
        subagents = {s["name"]: s for s in _build()["subagents"]}
        assert set(subagents) == {"researcher", "synthesizer"}
        assert subagents["researcher"]["tools"] == [{"type": "web_search"}]
        assert subagents["synthesizer"]["tools"] == []

    def test_the_input_mounts_only_this_flows_skills_with_consent_kept(self) -> None:
        message = HumanMessage(content="Update this report")
        agent_input = build_live_report_input(
            message, {"/attachments/r.md": {"content": ["x"]}}
        )
        assert agent_input["messages"] == [message]
        files = agent_input["files"]
        assert files["/attachments/r.md"] == {"content": ["x"]}
        skills = {p.split("/")[2] for p in files if p.startswith("/skills/")}
        assert skills == set(LIVE_REPORT_SKILLS)
        skill = str(files["/skills/live-reports/SKILL.md"]["content"])
        assert "consent" in skill.lower()
        assert INTERACTIVE_ONLY_START not in skill

    def test_every_skill_file_the_prompts_name_exists(self) -> None:
        prompts = SYSTEM_PROMPT + RESEARCHER_PROMPT + SYNTHESIZER_PROMPT
        named = set(re.findall(r"/skills/([\w./-]+\.md)", prompts))
        assert named, "the prompts should send the agents to the skill's files"
        for path in named:
            assert (_SKILLS_DIR / path).is_file(), path

    def test_the_researcher_knows_today_and_looks_after_the_cutoff(self) -> None:
        prompt = researcher_prompt(datetime(2026, 11, 6, tzinfo=UTC))
        assert "today (November 6, 2026)" in prompt
        assert "still true now" in prompt

    def test_turns_are_traced_under_their_own_name(self) -> None:
        config = live_report_run_config(thread_id="t-1", user_id="u-1")
        assert config["configurable"] == {"thread_id": "t-1"}
        assert config["run_name"] == "live_report_agent"
        assert config["metadata"]["langfuse_tags"] == ["live_report"]


class TestThreadAgents:
    def test_each_kind_reads_and_runs_through_its_own_agent(self) -> None:
        chat = thread_agent(ChatThreadKind.CHAT)
        live = thread_agent("live_report")
        assert chat.reader is chat_agent.chat_reader
        assert chat.build_agent is chat_agent.build_chat_agent
        assert live.reader is live_report_agent.live_report_reader
        assert (live.build_agent, live.build_input, live.run_config) == (
            build_live_report_agent,
            build_live_report_input,
            live_report_run_config,
        )


class TestWhatSubagentsMayTouch:
    """Enforced by the file tools: a page a researcher reads can carry instructions."""

    def test_a_researcher_writes_only_its_notes_and_never_reads_the_report(
        self,
    ) -> None:
        def check(operation: Any, path: str) -> str:
            return _check_fs_permission(RESEARCHER_PERMISSIONS, operation, path)

        assert check("write", "/live-report/research/F1.md") == "allow"
        assert check("write", "/live-report/research-plan.md") == "deny"
        assert check("write", "/live-report/research-brief.md") == "deny"
        assert check("read", "/attachments/report.md") == "deny"
        assert check("read", "/skills/live-reports/steps/research.md") == "allow"

    def test_the_synthesizer_writes_only_the_brief_and_the_addendum(self) -> None:
        def check(path: str) -> str:
            return _check_fs_permission(SYNTHESIZER_PERMISSIONS, "write", path)

        assert check("/live-report/research-brief.md") == "allow"
        assert check("/live-report/addendum.md") == "allow"
        assert check("/live-report/research-plan.md") == "deny"
        assert check("/live-report/research/F1.md") == "deny"
        # It reads the report: the brief and the addendum need it.
        assert (
            _check_fs_permission(SYNTHESIZER_PERMISSIONS, "read", "/attachments/r.md")
            == "allow"
        )

    def test_each_subagent_carries_its_rules(self) -> None:
        specs = {
            s["name"]: s
            for s in live_report_agent.live_report_subagents(
                resolve_chat_model("gpt-5.6-sol")
            )
        }
        assert specs["researcher"]["permissions"] is RESEARCHER_PERMISSIONS
        assert specs["synthesizer"]["permissions"] is SYNTHESIZER_PERMISSIONS
