"""Tests for the Word add-in's chat agent.

Run through a real deep agent over an in-memory checkpointer, with a scripted model,
because what matters is how turns fit together: the document is mounted when the pane
sends it and kept when it does not, the notes reach the agent but not the chat, and a
suggestion comes out of the stream with the id its card is found by.
"""

import base64
import json
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deepagents.backends.utils import file_data_to_string
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from lib.agents import word_chat_agent
from lib.agents.tools import word_suggestions
from lib.agents.tools.word_suggestions import SuggestionTarget
from lib.agents.word_chat_agent import (
    COMMENTS_PATH,
    DOCUMENT_PATH,
    MAX_SELECTION_CHARS,
    WordChatTurn,
    run_word_chat_turn,
    turn_input,
    turn_message,
)
from lib.models.file import FileRole
from lib.services.chat import thread_state
from lib.services.chat.history import to_ui_messages
from lib.services.microsoft.graph.documents import LoadedDocument
from lib.services.microsoft.word.chat_suggestions import ChatSuggestion
from lib.services.microsoft.word.handoffs import (
    HandoffEdit,
    HandoffItems,
    HandoffOutcome,
    ItemOutcome,
    Requester,
)

THREAD = uuid.uuid4()
DOCUMENT = LoadedDocument(
    name="Draft.docx",
    url="https://contoso.sharepoint.com/sites/Policy/Shared Documents/Draft.docx",
    markdown="## Findings\n\nThe policy is the only option.\n",
    comments=[("Ana", "Too strong?")],
)
TARGET = SuggestionTarget(
    requester=Requester(oid="oid-ana", tid="tid-contoso", upn="ana@contoso.com"),
    chat_thread_id=THREAD,
    document_name="Draft.docx",
    document_url=DOCUMENT.url,
    document_keys=[
        "path:contoso.sharepoint.com/sites/policy/shared documents/draft.docx"
    ],
)


class _ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        return self


def turn(text: str, **kwargs: Any) -> WordChatTurn:
    return WordChatTurn(thread_id=THREAD, text=text, **kwargs)


class TestTheMessage:
    def test_the_chat_shows_only_what_they_typed(self) -> None:
        message = turn_message(
            turn(
                " Is this right? ",
                document=DOCUMENT,
                selection="the only option",
                suggestion_news="[About your earlier suggestions: ...]",
            )
        )

        assert message.additional_kwargs["user_text"] == "Is this right?"
        content = str(message.content)
        assert content.startswith("Is this right?")
        assert "[About your earlier suggestions" in content
        assert f"read again for this message, at {DOCUMENT_PATH}" in content
        assert f"1 comments at {COMMENTS_PATH}" in content
        assert "selected in Word:\nthe only option" in content

    def test_without_a_document_nothing_is_said_about_one(self) -> None:
        content = str(turn_message(turn("And now?")).content)

        assert content == "And now?"

    def test_a_long_selection_is_cut(self) -> None:
        content = str(turn_message(turn("?", selection="x" * 10_000)).content)

        assert "x" * MAX_SELECTION_CHARS + "…" in content
        assert "x" * (MAX_SELECTION_CHARS + 1) not in content


class TestMounting:
    def test_the_document_and_its_comments_are_mounted(self) -> None:
        files = turn_input(turn("?", document=DOCUMENT))["files"]

        assert file_data_to_string(files[DOCUMENT_PATH]) == DOCUMENT.markdown
        assert file_data_to_string(files[COMMENTS_PATH]) == "Ana: Too strong?"

    def test_skills_that_only_search_the_web_are_left_out(self) -> None:
        files = turn_input(turn("?"))["files"]

        assert any(path.startswith("/skills/reviewer-2/") for path in files)
        assert not any(path.startswith("/skills/literature-review/") for path in files)
        assert DOCUMENT_PATH not in files


@pytest.fixture
def saver() -> Iterator[InMemorySaver]:
    memory = InMemorySaver()

    @asynccontextmanager
    async def get_checkpointer() -> Any:
        yield memory

    with (
        patch.object(word_chat_agent, "get_checkpointer", get_checkpointer),
        patch.object(thread_state, "get_checkpointer", get_checkpointer),
    ):
        yield memory


def scripted(*replies: AIMessage) -> Any:
    return patch.object(
        word_chat_agent,
        "build_llm",
        lambda *args, **kwargs: _ScriptedModel(
            messages=iter(replies), disable_streaming=True
        ),
    )


async def run(chat_turn: WordChatTurn) -> list[dict[str, Any]]:
    return [event async for event in run_word_chat_turn(chat_turn, TARGET)]


class TestATurn:
    @pytest.mark.asyncio
    async def test_a_suggestion_comes_back_with_its_id(
        self, saver: InMemorySaver
    ) -> None:
        stored_id = uuid.uuid4()
        call = {
            "name": "suggest_changes",
            "id": "call-1",
            "args": {
                "comments": [{"quote": "the only option", "comment": "Overclaims."}],
                "edits": [],
            },
        }
        with (
            scripted(
                AIMessage(content="", tool_calls=[call]),
                AIMessage(content="I suggested one comment."),
            ),
            patch.object(
                word_suggestions.handoffs, "create", AsyncMock(return_value=stored_id)
            ) as create,
        ):
            events = await run(turn("Comment on the findings", document=DOCUMENT))

        assert create.await_args is not None
        assert create.await_args.kwargs["chat_thread_id"] == THREAD
        assert "reference" not in create.await_args.kwargs, "nothing to post to Teams"
        results = [e for e in events if e["t"] == "tool_result"]
        assert json.loads(results[0]["result"])["suggestion_id"] == str(stored_id)
        # The scripted model does not stream, so there are no text deltas to check;
        # the call is announced as the pane's card expects it.
        calls = [e for e in events if e["t"] == "tool"]
        assert calls[0]["name"] == "suggest_changes" and calls[0]["id"] == "call-1"

    @pytest.mark.asyncio
    async def test_a_later_turn_keeps_the_document_it_was_not_sent(
        self, saver: InMemorySaver
    ) -> None:
        with scripted(AIMessage(content="one"), AIMessage(content="two")):
            await run(turn("first", document=DOCUMENT))
            await run(turn("second"))

        agent = word_chat_agent.build_word_chat_agent(saver, None, api_key="unused")
        snapshot = await agent.aget_state({"configurable": {"thread_id": str(THREAD)}})
        assert DOCUMENT_PATH in snapshot.values["files"]
        shown = to_ui_messages(snapshot.values["messages"])
        assert [m["content"] for m in shown if m["type"] == "human"] == [
            "first",
            "second",
        ]


@pytest.mark.asyncio
async def test_the_pane_reads_the_conversation_back_through_this_graph(
    saver: InMemorySaver,
) -> None:
    """The route reads history through ``thread_state`` with ``word_chat_reader``:
    the graph that wrote the thread is the one that replays it."""

    with scripted(AIMessage(content="one")):
        await run(turn("first", document=DOCUMENT))

    reader = word_chat_agent.word_chat_reader
    messages = await thread_state.load_thread_messages(str(THREAD), reader=reader)
    document = await thread_state.read_thread_file(
        str(THREAD), DOCUMENT_PATH, reader=reader
    )

    assert [m.type for m in messages] == ["human", "ai"]
    assert document == DOCUMENT.markdown


class TestQuotesAreCheckedFirst:
    @pytest.mark.asyncio
    async def test_a_quote_word_would_not_find_stores_nothing(
        self, saver: InMemorySaver
    ) -> None:
        call = {
            "name": "suggest_changes",
            "id": "call-1",
            "args": {
                "comments": [{"quote": "a sentence not in it", "comment": "?"}],
                "edits": [{"quote": "the only option", "replacement": "one option"}],
            },
        }
        with (
            scripted(AIMessage(content="", tool_calls=[call]), AIMessage(content="ok")),
            patch.object(word_suggestions.handoffs, "create", AsyncMock()) as create,
        ):
            events = await run(turn("Comment on it", document=DOCUMENT))

        create.assert_not_awaited()
        said = json.loads(next(e for e in events if e["t"] == "tool_result")["result"])
        assert said["saved"] is False
        assert said["problems"] == [
            "comment on “a sentence not in it”: "
            + word_suggestions.PROBLEMS["not_found"]
        ]


class TestWithoutTheDocument:
    @pytest.mark.asyncio
    async def test_nothing_is_suggested_unchecked(self, saver: InMemorySaver) -> None:
        call = {
            "name": "suggest_changes",
            "id": "call-1",
            "args": {"comments": [{"quote": "any words", "comment": "?"}], "edits": []},
        }
        with (
            scripted(AIMessage(content="", tool_calls=[call]), AIMessage(content="ok")),
            patch.object(word_suggestions.handoffs, "create", AsyncMock()) as create,
        ):
            events = await run(turn("Comment on it"))

        create.assert_not_awaited()
        said = json.loads(next(e for e in events if e["t"] == "tool_result")["result"])
        assert said["problems"] == [word_suggestions.NO_DOCUMENT]


def test_subagents_can_view_images_but_not_suggest_changes() -> None:
    """What a subagent stores never reaches the pane's conversation: no card shows it.

    Looking at the document's images is safe to share: the tool is bound to this
    conversation, so either agent sees only the images the conversation holds.
    """

    with patch.object(word_chat_agent, "build_deep_agent") as build:
        word_chat_agent.build_word_chat_agent(InMemorySaver(), TARGET, api_key="unused")

    (subagent,) = build.call_args.kwargs["subagents"]
    assert subagent["name"] == "general-purpose"
    assert [tool.name for tool in subagent["tools"]] == ["view_image"]
    assert [tool.name for tool in build.call_args.kwargs["tools"]] == [
        "suggest_changes",
        "ask_to_apply",
        "view_image",
    ]
    assert "draftdetective://" in build.call_args.kwargs["system_prompt"]


class TestACardHoldsAtMostItsLimit:
    @pytest.mark.asyncio
    async def test_items_left_out_are_reported(self, saver: InMemorySaver) -> None:
        quote = "the only option"
        edits = [{"quote": quote, "replacement": "one option"}] * 2
        call = {
            "name": "suggest_changes",
            "id": "call-1",
            "args": {"comments": [], "edits": edits},
        }
        with (
            scripted(AIMessage(content="", tool_calls=[call]), AIMessage(content="ok")),
            patch.object(
                word_suggestions.handoffs,
                "create",
                AsyncMock(return_value=uuid.uuid4()),
            ),
        ):
            events = await run(turn("Fix it", document=DOCUMENT))

        said = json.loads(next(e for e in events if e["t"] == "tool_result")["result"])
        assert said["edits"] == 1
        assert "1 item(s) were left out" in said["message"]


def suggest(call_id: str, *edits: tuple[str, str]) -> dict[str, Any]:
    return {
        "name": "suggest_changes",
        "id": call_id,
        "args": {
            "comments": [],
            "edits": [{"quote": quote, "replacement": new} for quote, new in edits],
        },
    }


def results(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(e["result"]) for e in events if e["t"] == "tool_result"]


TWO_PARAGRAPHS = LoadedDocument(
    name="Draft.docx",
    url=DOCUMENT.url,
    markdown="The policy is the only option.\n\nWe recieve funding twice.\n",
)


class TestOneCardPerAnswer:
    @pytest.mark.asyncio
    async def test_calls_in_one_answer_add_to_the_same_card(
        self, saver: InMemorySaver
    ) -> None:
        card = uuid.uuid4()
        with (
            scripted(
                AIMessage(
                    content="", tool_calls=[suggest("c1", ("only option", "one"))]
                ),
                AIMessage(
                    content="", tool_calls=[suggest("c2", ("recieve", "receive"))]
                ),
                AIMessage(content="Two edits."),
            ),
            patch.object(
                word_suggestions.handoffs, "create", AsyncMock(return_value=card)
            ) as create,
            patch.object(
                word_suggestions.chat_suggestions,
                "replace_items",
                AsyncMock(return_value=True),
            ) as replace,
        ):
            events = await run(turn("Fix both", document=TWO_PARAGRAPHS))

        create.assert_awaited_once()
        assert replace.await_args is not None
        merged = replace.await_args.args[2]
        assert [edit.quote for edit in merged.edits] == ["only option", "recieve"]
        first, second = results(events)
        assert (first["card"], second["card"]) == ("new", "added")
        assert first["suggestion_id"] == second["suggestion_id"] == str(card)
        assert (second["added"], second["edits"]) == (1, 2)

    @pytest.mark.asyncio
    async def test_a_card_that_can_no_longer_change_is_left_and_a_new_one_opened(
        self, saver: InMemorySaver
    ) -> None:
        with (
            scripted(
                AIMessage(
                    content="", tool_calls=[suggest("c1", ("only option", "one"))]
                ),
                AIMessage(
                    content="", tool_calls=[suggest("c2", ("recieve", "receive"))]
                ),
                AIMessage(content="ok"),
            ),
            patch.object(
                word_suggestions.handoffs,
                "create",
                AsyncMock(side_effect=[uuid.uuid4(), uuid.uuid4()]),
            ) as create,
            patch.object(
                word_suggestions.chat_suggestions,
                "replace_items",
                AsyncMock(return_value=False),  # applying has begun
            ),
        ):
            events = await run(turn("Fix both", document=TWO_PARAGRAPHS))

        assert create.await_count == 2
        assert [r["card"] for r in results(events)] == ["new", "new"]

    @pytest.mark.asyncio
    async def test_two_calls_at_once_open_one_card(self, saver: InMemorySaver) -> None:
        both = [suggest("c1", ("only option", "one")), suggest("c2", ("recieve", "x"))]
        with (
            scripted(AIMessage(content="", tool_calls=both), AIMessage(content="ok")),
            patch.object(
                word_suggestions.handoffs,
                "create",
                AsyncMock(return_value=uuid.uuid4()),
            ) as create,
            patch.object(
                word_suggestions.chat_suggestions,
                "replace_items",
                AsyncMock(return_value=True),
            ),
        ):
            events = await run(turn("Fix both", document=TWO_PARAGRAPHS))

        create.assert_awaited_once()
        assert sorted(r["card"] for r in results(events)) == ["added", "new"]

    @pytest.mark.asyncio
    async def test_an_edit_already_on_the_card_is_not_added_twice(
        self, saver: InMemorySaver
    ) -> None:
        with (
            scripted(
                AIMessage(
                    content="", tool_calls=[suggest("c1", ("recieve", "receive"))]
                ),
                AIMessage(content="", tool_calls=[suggest("c2", ("recieve", "get"))]),
                AIMessage(content="ok"),
            ),
            patch.object(
                word_suggestions.handoffs,
                "create",
                AsyncMock(return_value=uuid.uuid4()),
            ),
            patch.object(
                word_suggestions.chat_suggestions,
                "replace_items",
                AsyncMock(return_value=True),
            ),
        ):
            events = await run(turn("Fix it", document=TWO_PARAGRAPHS))

        second = results(events)[1]
        assert (second["added"], second["edits"]) == (0, 1)
        assert "1 item(s) were left out" in second["message"]


def settled(card_id: uuid.UUID, status: str, applied: int = 0) -> ChatSuggestion:
    items = HandoffItems(
        edits=[HandoffEdit(quote="the only option", replacement="one")]
    )
    outcome = HandoffOutcome(
        items=[ItemOutcome(kind="edit", quote="the only option", applied=applied > 0)]
    )
    return ChatSuggestion(
        id=card_id,
        chat_thread_id=THREAD,
        status=status,  # type: ignore[arg-type]  # the four statuses, as plain strings
        document_name="Draft.docx",
        document_url=DOCUMENT.url,
        items=items,
        outcome=outcome if status == "applied" else None,
        created_at=datetime.now(UTC),
        finished_at=None if status == "pending" else datetime.now(UTC),
    )


class TestAskingToApply:
    @pytest.mark.asyncio
    async def test_the_answer_pauses_on_its_card_and_carries_on_with_the_outcome(
        self, saver: InMemorySaver
    ) -> None:
        card = uuid.uuid4()
        ask = {"name": "ask_to_apply", "id": "c2", "args": {"suggestion_id": str(card)}}
        lookups = AsyncMock(
            side_effect=[settled(card, "pending"), settled(card, "applied", applied=1)]
        )
        with (
            scripted(
                AIMessage(
                    content="", tool_calls=[suggest("c1", ("only option", "one"))]
                ),
                AIMessage(content="One edit for you.", tool_calls=[ask]),
                AIMessage(content="It was applied."),
            ),
            patch.object(
                word_suggestions.handoffs, "create", AsyncMock(return_value=card)
            ),
            patch.object(word_suggestions.chat_suggestions, "suggestion_for", lookups),
            patch.object(
                word_suggestions.chat_suggestions, "mark_heard", AsyncMock()
            ) as heard,
        ):
            first = await run(turn("Fix it", document=DOCUMENT))
            waiting = await word_chat_agent.pending_suggestion(THREAD)
            rest = [
                event
                async for event in word_chat_agent.run_word_chat_resume(THREAD, TARGET)
            ]

        assert first[-1]["t"] == "interrupt"
        assert first[-1]["v"] == [{"suggestion_id": str(card)}]
        assert waiting == card
        told = [e["result"] for e in rest if e["t"] == "tool_result"]
        assert told and "1 of 1" in told[0]
        assert not any(e["t"] == "interrupt" for e in rest)
        assert await word_chat_agent.pending_suggestion(THREAD) is None
        # Told now, so the next message does not report it again as news.
        heard.assert_awaited_once_with([card])

    @pytest.mark.asyncio
    async def test_a_card_of_another_conversation_is_not_asked_about(
        self, saver: InMemorySaver
    ) -> None:
        card = uuid.uuid4()
        elsewhere = settled(card, "pending").model_copy(
            update={"chat_thread_id": uuid.uuid4()}
        )
        ask = {"name": "ask_to_apply", "id": "c1", "args": {"suggestion_id": str(card)}}
        with (
            scripted(AIMessage(content="", tool_calls=[ask]), AIMessage(content="ok")),
            patch.object(
                word_suggestions.chat_suggestions,
                "suggestion_for",
                AsyncMock(return_value=elsewhere),
            ),
        ):
            events = await run(turn("Apply it"))

        assert not any(e["t"] == "interrupt" for e in events)
        assert "no card with that id" in results_text(events)

    @pytest.mark.asyncio
    async def test_a_new_message_while_paused_moves_on(
        self, saver: InMemorySaver
    ) -> None:
        card = uuid.uuid4()
        ask = {"name": "ask_to_apply", "id": "c1", "args": {"suggestion_id": str(card)}}
        with (
            scripted(
                AIMessage(content="", tool_calls=[ask]),
                AIMessage(content="Answering that instead."),
            ),
            patch.object(
                word_suggestions.chat_suggestions,
                "suggestion_for",
                AsyncMock(return_value=settled(card, "pending")),
            ),
        ):
            await run(turn("Apply it", document=DOCUMENT))
            assert await word_chat_agent.pending_suggestion(THREAD) == card
            events = await run(turn("Never mind: what is the main claim?"))

        # The open call is closed for it ("did not complete") and the turn runs.
        assert not any(e["t"] == "interrupt" for e in events)
        assert any(e["t"] == "message_end" for e in events)
        assert await word_chat_agent.pending_suggestion(THREAD) is None


def results_text(events: list[dict[str, Any]]) -> str:
    return " ".join(str(e["result"]) for e in events if e["t"] == "tool_result")


class TestViewingAnImage:
    @pytest.mark.asyncio
    async def test_the_stored_conversation_keeps_a_note_not_the_image(
        self, saver: InMemorySaver, tmp_path: Path
    ) -> None:
        """Seen once, an image would otherwise sit in the checkpoint for good, megabytes
        each, and go back to the model on every later turn."""

        picture = tmp_path / "figure.png"
        picture.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 4000)
        image_id = uuid.uuid4()
        row = MagicMock(
            id=image_id,
            conversation_id=THREAD,
            project_id=None,
            role=FileRole.EXTRACTED_IMAGE,
            file_type="image/png",
            file_size=picture.stat().st_size,
            file_path=str(picture),
        )
        look = {
            "name": "view_image",
            "id": "c1",
            "args": {"image_reference": f"draftdetective://{image_id}"},
        }
        with (
            scripted(
                AIMessage(content="", tool_calls=[look]),
                AIMessage(content="A radar chart."),
            ),
            patch(
                "lib.agents.tools.view_image.get_file_by_id",
                AsyncMock(return_value=row),
            ),
        ):
            await run(turn("What does Figure 3 show?", document=DOCUMENT))

        agent = word_chat_agent.build_word_chat_agent(saver, None, api_key="unused")
        snapshot = await agent.aget_state({"configurable": {"thread_id": str(THREAD)}})
        stored = str(snapshot.values["messages"])
        assert "bytes omitted" in stored
        assert base64.b64encode(picture.read_bytes()).decode() not in stored
