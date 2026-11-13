"""A shared Teams thread never hands one person's document to another.

One Teams conversation is one LangGraph thread, so a document opened for A stays
mounted, and A's reads of it stay in the history, when B asks next. These tests run the
real agent and checkpointer over two turns, with a scripted model that does what a
model talked out of ``check_document`` would do: read the copy straight away. Whether
B gets the text must not depend on the model.
"""

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from lib.agents import teams_agent
from lib.agents.tools import sharepoint
from lib.services.chat.history import thread_config
from lib.services.microsoft.graph.client import GraphError
from lib.services.microsoft.graph.documents import LoadedDocument

THREAD = "19:shared@thread.v2"
URL = "https://x.sharepoint.com/sites/X/plan.docx"
PATH = "/documents/plan.md"
SECRET = "The confidential plan is to acquire Contoso."
TOKEN_A = "token-of-a"
TOKEN_B = "token-of-b"


class _ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        return self


def calls(name: str, **args: Any) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"{name}-{uuid.uuid4()}"}],
    )


@pytest.fixture
def saver() -> Iterator[InMemorySaver]:
    memory = InMemorySaver()

    @asynccontextmanager
    async def get_checkpointer() -> Any:
        yield memory

    document = LoadedDocument(
        name="plan.docx", url=URL, markdown=f"# Plan\n\n{SECRET}\n", last_modified="t1"
    )

    async def resolve(url: str, *, token: str) -> dict[str, Any]:
        if token != TOKEN_A:
            raise GraphError("403 accessDenied")
        return {"name": "plan.docx", "lastModifiedDateTime": "t1"}

    with (
        patch.object(teams_agent, "get_checkpointer", get_checkpointer),
        patch.object(teams_agent, "asker", AsyncMock(return_value=None)),
        patch.object(teams_agent, "has_deployment_key", return_value=True),
        patch.object(teams_agent.conversations, "for_teams", AsyncMock()),
        patch.object(sharepoint.documents, "load", AsyncMock(return_value=document)),
        patch.object(sharepoint.client, "resolve", AsyncMock(side_effect=resolve)),
        patch.object(sharepoint.file_images, "add_conversation_images", AsyncMock()),
        patch.object(sharepoint.file_images, "drop_conversation_images", AsyncMock()),
    ):
        yield memory


async def ask(token: str, *replies: AIMessage) -> None:
    model = _ScriptedModel(messages=iter(replies), disable_streaming=True)
    with patch.object(teams_agent, "build_llm", return_value=model):
        answer = await teams_agent.answer_question(
            "about the plan", graph_token=token, thread_id=THREAD
        )
    assert not answer.failed, answer.error


async def history(saver: InMemorySaver) -> list[BaseMessage]:
    graph = teams_agent.build_deep_agent(
        model=_ScriptedModel(messages=iter([])), tools=[], checkpointer=saver
    )
    snapshot = await graph.aget_state(thread_config(THREAD))
    return list(snapshot.values.get("messages") or [])


def tool_results(messages: list[BaseMessage]) -> list[str]:
    return [str(m.content) for m in messages if isinstance(m, ToolMessage)]


async def a_opens_and_reads(saver: InMemorySaver) -> None:
    await ask(
        TOKEN_A,
        calls("open_document", url=URL, path=PATH),
        calls("read_file", file_path=PATH),
        AIMessage(content="It is about an acquisition."),
    )
    assert any(SECRET in result for result in tool_results(await history(saver)))


class TestSomebodyWithoutAccessAsksNext:
    @pytest.mark.asyncio
    async def test_the_copy_opened_for_somebody_else_cannot_be_read(
        self, saver: InMemorySaver
    ) -> None:
        await a_opens_and_reads(saver)

        await ask(
            TOKEN_B,
            calls("read_file", file_path=PATH),
            AIMessage(content="Here it is."),
        )

        last_read = tool_results(await history(saver))[-1]
        assert SECRET not in last_read

    @pytest.mark.asyncio
    async def test_what_was_read_for_somebody_else_leaves_the_history(
        self, saver: InMemorySaver
    ) -> None:
        await a_opens_and_reads(saver)

        await ask(TOKEN_B, AIMessage(content="Here is what I read earlier."))

        assert not any(SECRET in r for r in tool_results(await history(saver)))


class TestSomebodyWithAccessAsksNext:
    @pytest.mark.asyncio
    async def test_the_copy_is_still_there_for_them(self, saver: InMemorySaver) -> None:
        await a_opens_and_reads(saver)

        await ask(
            TOKEN_A,
            calls("read_file", file_path=PATH),
            AIMessage(content="Still about an acquisition."),
        )

        assert SECRET in tool_results(await history(saver))[-1]


# What happened when, across two runs at once.
ORDER: list[str] = []


class _SlowModel(_ScriptedModel):
    """Answers after a pause, noting each answer, so a run lasts long enough for
    another to try to start inside it."""

    async def _agenerate(self, *args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0.05)
        ORDER.append("A's model")
        return await super()._agenerate(*args, **kwargs)


class TestTwoQuestionsAtOnce:
    @pytest.mark.asyncio
    async def test_the_second_is_checked_only_once_the_first_has_finished(
        self, saver: InMemorySaver
    ) -> None:
        """Otherwise the first could mount a copy after the second was checked."""

        await a_opens_and_reads(saver)
        order = ORDER
        order.clear()
        real = teams_agent.withhold_unreadable

        async def checked(state: Any, token: str, conversation: Any) -> Any:
            order.append(f"check {token}")
            return await real(state, token, conversation)

        a_model = _SlowModel(
            messages=iter(
                [
                    calls("open_document", url=URL, path=PATH),
                    AIMessage(content="Reopened."),
                ]
            ),
            disable_streaming=True,
        )
        b_model = _ScriptedModel(
            messages=iter([calls("read_file", file_path=PATH), AIMessage(content="?")]),
            disable_streaming=True,
        )
        with (
            patch.object(teams_agent, "withhold_unreadable", checked),
            patch.object(teams_agent, "build_llm", side_effect=[a_model, b_model]),
        ):
            await asyncio.gather(
                teams_agent.answer_question("q", graph_token=TOKEN_A, thread_id=THREAD),
                teams_agent.answer_question("q", graph_token=TOKEN_B, thread_id=THREAD),
            )

        assert order == [
            f"check {TOKEN_A}",
            "A's model",
            "A's model",
            f"check {TOKEN_B}",
        ]
        assert SECRET not in tool_results(await history(saver))[-1]
