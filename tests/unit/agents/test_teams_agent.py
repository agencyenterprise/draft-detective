"""Tests for the agent that answers Teams questions.

It differs from the Word agent in one structural way: it is not given a document.
Deciding which to open, and where to put it, is its own job -- so what is asserted here
is that it gets the tools and the candidate links, and that only the skills are mounted
up front, since the skills middleware reads those once before the run and a tool cannot
supply them later.

The prompt assertions are narrow on purpose. A link is the only way to reach a
document, and the failure they guard against is the model filling that gap itself:
answering from a file name, or guessing at a URL.

A conversation persists, so documents opened in earlier turns are still here. That is
deliberate, and it is why the agent is given ``check_document``: a kept copy may have
been edited since, and may have been opened for somebody else in the thread.
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from lib.agents.teams_agent import answer_question, answer_text
from lib.agents.tools import sharepoint

# Every run reads as somebody; the tests do not care who.
TOKEN = "a-user-token"
THREAD = "19:abc@thread.tacv2;messageid=1754"
DOCUMENT_URL = "https://x.sharepoint.com/sites/X/a.docx"


def agent_returning(answer: str, state: Optional[dict[str, Any]] = None) -> MagicMock:
    """A deep agent whose last message is the answer.

    Returns the whole history the way a checkpointed run does -- the question and then
    the reply -- because what is read back out is the messages rather than a structured
    field.
    """

    fake = MagicMock()
    fake.ainvoke = AsyncMock(
        return_value={
            "messages": [HumanMessage(content="a question"), AIMessage(content=answer)],
        }
    )
    snapshot = MagicMock()
    snapshot.values = state if state is not None else {}
    fake.aget_state = AsyncMock(return_value=snapshot)
    return fake


@pytest.fixture(autouse=True)
def checkpointer() -> Any:
    """Stand in for the saver, since every answer belongs to a thread.

    Nothing here is about the pool -- ``test_checkpointer.py`` covers that -- but every
    call opens one, so it is patched for the whole module rather than per test.
    """

    saver = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=saver)
    context.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "lib.agents.teams_agent.get_checkpointer", MagicMock(return_value=context)
    ) as opened:
        yield opened


class TestWhatTheAgentIsGiven:
    @pytest.mark.asyncio
    async def test_no_document_is_mounted_up_front(self) -> None:
        """Documents arrive through the tool; only skills are mounted."""

        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "does this overclaim?", graph_token=TOKEN, thread_id=THREAD
            )

        files = agent.ainvoke.call_args[0][0]["files"]
        assert not any(path.startswith("/documents/") for path in files)
        assert any(path.startswith("/skills/") for path in files), (
            "skills must be mounted before the run; a tool cannot add them"
        )

    @pytest.mark.asyncio
    async def test_the_asker_is_named_in_the_prompt(self) -> None:
        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "hello?",
                graph_token=TOKEN,
                thread_id=THREAD,
                asked_by="Carlos Bonetti",
            )

        assert "Carlos Bonetti" in agent.ainvoke.call_args[0][0]["messages"][0].content


class TestReadingTheAnswerOutOfTheMessages:
    """No ``response_format``: the answer is the last thing the model said.

    Which puts the burden on reading it back correctly, and a persisted thread makes one
    of those cases dangerous rather than merely wrong.
    """

    def test_the_last_thing_said_is_the_answer(self) -> None:
        assert (
            answer_text(
                [
                    HumanMessage(content="first?"),
                    AIMessage(content="an old answer"),
                    HumanMessage(content="second?"),
                    AIMessage(content="the new answer"),
                ]
            )
            == "the new answer"
        )

    def test_markdown_survives_intact(self) -> None:
        """The reason for dropping the JSON wrapper, so it is worth asserting."""

        markdown = '## Findings\n\n1. **GDP** is undefined at "the total GDP" [70]\n'

        assert answer_text([HumanMessage(content="?"), AIMessage(content=markdown)]) == (
            markdown.strip()
        )

    def test_reasoning_blocks_are_not_part_of_the_answer(self) -> None:
        """Reasoning-model output arrives as blocks beside the text."""

        message = AIMessage(
            content=[
                {"type": "reasoning", "summary": "let me think about the abbreviations"},
                {"type": "text", "text": "GDP is never defined."},
            ]
        )

        assert answer_text([HumanMessage(content="?"), message]) == "GDP is never defined."

    def test_a_turn_ending_in_a_tool_call_is_not_an_answer(self) -> None:
        """It reached the recursion limit mid-work, so there is nothing to post."""

        working = AIMessage(
            content="",
            tool_calls=[{"name": "open_document", "args": {"url": "u"}, "id": "1"}],
        )

        assert answer_text([HumanMessage(content="?"), working]) == ""

    def test_it_never_reaches_back_into_an_earlier_turn(self) -> None:
        """The dangerous case, and only possible because the thread is persisted.

        A turn that produces no text must come back empty rather than re-posting the
        previous turn's answer as though it were a reply to the new question.
        """

        history = [
            HumanMessage(content="what does paragraph 12 say?"),
            AIMessage(content="Paragraph 12 says the budget tripled."),
            HumanMessage(content="and paragraph 13?"),
            AIMessage(
                content="",
                tool_calls=[{"name": "read_file", "args": {}, "id": "2"}],
            ),
            ToolMessage(content="…", tool_call_id="2"),
        ]

        assert answer_text(history) == ""

    def test_nothing_at_all_is_empty_rather_than_an_error(self) -> None:
        assert answer_text([]) == ""


class TestTheAnswer:
    @pytest.mark.asyncio
    async def test_a_normal_answer_comes_back(self) -> None:
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent",
            return_value=agent_returning("It overclaims in two places."),
        ):
            answer = await answer_question(
                "does this overclaim?",
                graph_token=TOKEN,
                thread_id=THREAD,
            )

        assert answer.failed is False
        assert answer.text == "It overclaims in two places."

    @pytest.mark.asyncio
    async def test_an_empty_answer_is_a_failure_rather_than_a_blank_post(self) -> None:
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent",
            return_value=agent_returning("   "),
        ):
            answer = await answer_question(
                "does this overclaim?",
                graph_token=TOKEN,
                thread_id=THREAD,
            )

        assert answer.failed is True and answer.text == ""

    @pytest.mark.asyncio
    async def test_a_crash_is_reported_rather_than_raised(self) -> None:
        """The caller is a background task with nobody to hand an exception to."""

        broken = agent_returning("never gets this far")
        broken.ainvoke = AsyncMock(side_effect=RuntimeError("upstream timeout"))
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=broken
        ):
            answer = await answer_question(
                "does this overclaim?",
                graph_token=TOKEN,
                thread_id=THREAD,
            )

        assert answer.failed is True and "upstream timeout" in (answer.error or "")


class TestContinuingAConversation:
    """One Teams thread is one LangGraph thread, which is the whole feature."""

    @pytest.mark.asyncio
    async def test_one_id_keys_the_checkpoint_and_the_langfuse_session(self) -> None:
        """Both, from one parameter: a conversation is findable in the trace view under
        the same id it is stored under."""

        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "and the second one?", graph_token=TOKEN, thread_id=THREAD
            )

        config = agent.ainvoke.call_args.kwargs["config"]
        assert config["configurable"]["thread_id"] == THREAD
        assert config["metadata"]["langfuse_session_id"] == THREAD

    @pytest.mark.asyncio
    async def test_a_checkpointer_is_given_to_the_agent(self) -> None:
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent",
            return_value=agent_returning("an answer"),
        ) as build:
            await answer_question(
                "and the second one?", graph_token=TOKEN, thread_id=THREAD
            )

        assert build.call_args.kwargs["checkpointer"] is not None

    @pytest.mark.asyncio
    async def test_a_thread_is_not_optional(self) -> None:
        """No opting out, so there is no second path where a document is unchecked."""

        # Loosely typed so that omitting the argument -- the thing under test -- does not
        # need a type: ignore for what mypy is right to reject.
        called: Any = answer_question

        with pytest.raises(TypeError, match="thread_id"):
            await called("does this overclaim?", graph_token=TOKEN)

    @pytest.mark.asyncio
    async def test_the_system_prompt_is_not_a_message(self) -> None:
        """It would be checkpointed, and re-appended on every single turn."""

        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ) as build:
            await answer_question(
                "does this overclaim?", graph_token=TOKEN, thread_id=THREAD
            )

        messages = agent.ainvoke.call_args[0][0]["messages"]
        assert len(messages) == 1, "only the new question belongs in a persisted thread"
        assert messages[0].type == "human"
        assert "Draft Detective" in build.call_args.kwargs["system_prompt"]


class TestTheLinksHandedOver:
    """Every link in the message, as candidates. The agent decides which is meant."""

    @pytest.mark.asyncio
    async def test_one_link_is_named_in_the_prompt(self) -> None:
        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "is this right?",
                graph_token=TOKEN,
                thread_id=THREAD,
                document_urls=[DOCUMENT_URL],
            )

        prompt = agent.ainvoke.call_args[0][0]["messages"][0].content
        assert DOCUMENT_URL in prompt
        assert "They linked to this document" in prompt

    @pytest.mark.asyncio
    async def test_several_links_are_all_offered(self) -> None:
        """"Compare these two" is unanswerable if only the first survives."""

        second = "https://x.sharepoint.com/sites/X/b.docx"
        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "compare these",
                graph_token=TOKEN,
                thread_id=THREAD,
                document_urls=[DOCUMENT_URL, second],
            )

        prompt = agent.ainvoke.call_args[0][0]["messages"][0].content
        assert DOCUMENT_URL in prompt and second in prompt
        assert "They linked to these documents" in prompt

    @pytest.mark.asyncio
    async def test_no_links_says_nothing_about_them(self) -> None:
        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ):
            await answer_question(
                "what can you do?", graph_token=TOKEN, thread_id=THREAD
            )

        prompt = agent.ainvoke.call_args[0][0]["messages"][0].content
        assert "They linked to" not in prompt

    @pytest.mark.asyncio
    async def test_nothing_is_loaded_before_the_agent_runs(self) -> None:
        """The agent opens what it needs. A link in the message is not a decision.

        A question about a document nobody asked about would otherwise cost a download
        every turn -- and the router would be choosing, which is what it cannot do well.
        """

        load = AsyncMock()
        agent = agent_returning("an answer")
        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent", return_value=agent
        ), patch.object(sharepoint.documents, "load", load):
            await answer_question(
                "what can you do?",
                graph_token=TOKEN,
                thread_id=THREAD,
                document_urls=[DOCUMENT_URL],
            )

        assert load.await_count == 0
        assert agent.ainvoke.call_args[0][0]["files"].keys() == {
            path for path in agent.ainvoke.call_args[0][0]["files"] if "/skills/" in path
        }, "skills only; documents arrive through the tool"


class TestTheToolsTheAgentGets:
    @pytest.mark.asyncio
    async def test_it_can_open_and_check_a_document(self) -> None:
        """Checking is what makes a kept copy safe to use in a later turn."""

        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent",
            return_value=agent_returning("an answer"),
        ) as build:
            await answer_question("hello?", graph_token=TOKEN, thread_id=THREAD)

        assert {tool.name for tool in build.call_args.kwargs["tools"]} == {
            "open_document",
            "check_document",
        }

    @pytest.mark.asyncio
    async def test_both_tools_read_as_the_asker(self) -> None:
        """One process serves many people, so neither tool may outlive its identity.

        Asserted by driving the tools the agent was actually handed, rather than by
        trusting that the factories were called with the right token.
        """

        opened = MagicMock(
            markdown="body", comments=[], name="a.docx", lines=1, last_modified="then"
        )
        load = AsyncMock(return_value=opened)
        resolve = AsyncMock(return_value={"name": "a.docx"})

        with patch("lib.agents.teams_agent.build_llm"), patch(
            "lib.agents.teams_agent.build_deep_agent",
            return_value=agent_returning("an answer"),
        ) as build:
            await answer_question("hello?", graph_token="carlos", thread_id=THREAD)

            tools = {tool.name: tool for tool in build.call_args.kwargs["tools"]}
            with patch.object(sharepoint.documents, "load", load):
                await tools["open_document"].coroutine(
                    "https://x/a.docx",
                    "/documents/a.md",
                    MagicMock(tool_call_id="call_1"),
                )
            with patch.object(sharepoint.client, "resolve", resolve):
                await tools["check_document"].coroutine("https://x/a.docx")

        assert load.await_args is not None
        assert load.await_args.kwargs["token"] == "carlos"
        assert resolve.await_args is not None
        assert resolve.await_args.kwargs["token"] == "carlos"


class TestThePrompt:
    def test_it_forbids_answering_from_a_name_alone(self) -> None:
        from lib.agents.teams_agent import SYSTEM_PROMPT

        assert "Open a document before answering" in SYSTEM_PROMPT

    def test_a_link_is_stated_as_the_only_way_to_reach_a_document(self) -> None:
        """The behaviour most likely to drift, since searching feels helpful."""

        from lib.agents.teams_agent import SYSTEM_PROMPT

        assert "A link is the only way to reach a document" in SYSTEM_PROMPT
        assert "must not guess at a URL" in SYSTEM_PROMPT

    def test_it_requires_asking_for_the_link_when_only_a_name_is_given(self) -> None:
        from lib.agents.teams_agent import SYSTEM_PROMPT

        assert "ask them to paste it" in SYSTEM_PROMPT

    def test_it_still_answers_questions_that_need_no_document(self) -> None:
        """Asking for a link to answer "what can you do?" would be a regression."""

        from lib.agents.teams_agent import SYSTEM_PROMPT

        assert "Some questions need no document at all" in SYSTEM_PROMPT
