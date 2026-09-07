"""Tests for the construction both document-review deep agents share.

These moved out of ``test_word_agent.py`` along with the code. What they cover is
what would break silently for *both* agents at once: the reasoning summary that makes
a wrong answer inspectable in Langfuse, the shared rate limiter, and the mounting of
the document and skills at the paths every skill's line numbers are defined against.
"""

from unittest.mock import patch

from lib.agents.deep_agent_setup import (
    DEFAULT_MODEL,
    build_agent_files,
    build_llm,
    build_skill_files,
    number_paragraphs,
    tool_names,
)


class TestModelConstruction:
    def test_reasoning_summary_is_requested(self) -> None:
        """The summary shows up in Langfuse, so a wrong answer can be inspected."""

        with patch("lib.agents.deep_agent_setup.init_chat_model") as init:
            build_llm(DEFAULT_MODEL, api_key="sk-test")

        kwargs = init.call_args.kwargs
        assert kwargs["reasoning"] == {"effort": "medium", "summary": "auto"}
        assert kwargs["temperature"] == 0.0
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
    def test_mounts_the_document_and_the_skills(self) -> None:
        files = build_agent_files("the document text")
        assert "/main.md" in files
        skills = [path for path in files if path.startswith("/skills/")]
        assert len(skills) > 10, "the project's skills should be mounted"
        assert any(path.endswith("/SKILL.md") for path in skills)

    def test_the_document_is_readable_by_the_agent(self) -> None:
        files = build_agent_files("the document text")
        assert "the document text" in str(files["/main.md"]["content"])

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


class TestNumberingParagraphs:
    def test_each_paragraph_carries_its_index(self) -> None:
        """The index is an exact handle back to the paragraph, not a search term."""

        assert number_paragraphs(["First.", "Second."]) == "[0] First.\n\n[1] Second."

    def test_no_paragraphs_is_not_an_error(self) -> None:
        assert number_paragraphs([]) == ""


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
