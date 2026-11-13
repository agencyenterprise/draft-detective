"""What a shared thread withholds from somebody who cannot read what it holds.

The two-turn runs are in ``test_teams_shared_thread.py``; these pin the rules the runs
depend on, which a scripted model would rarely reach.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from deepagents.backends.utils import create_file_data
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)

from lib.agents import shared_thread_access
from lib.agents.shared_thread_access import (
    opened_documents,
    public_history,
    withhold_unreadable,
)
from lib.services.microsoft.graph.client import GraphError

OURS = "https://x/ours.docx"
THEIRS = "https://x/theirs.docx"
CONVERSATION = uuid.uuid4()


def opening(call_id: str, url: str, path: str, result: str) -> list[BaseMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "open_document",
                    "args": {"url": url, "path": path},
                    "id": call_id,
                }
            ],
        ),
        ToolMessage(content=result, tool_call_id=call_id),
    ]


class TestWhereEachCopyCameFrom:
    def test_a_failed_reopen_does_not_relabel_the_copy_at_that_path(self) -> None:
        """Otherwise B could reopen a link B can read at A's path, fail to load it, and
        have A's copy checked against B's link."""

        messages = [
            *opening(
                "1", THEIRS, "/documents/a.md", "Opened 'a.docx' at /documents/a.md"
            ),
            *opening("2", OURS, "/documents/a.md", "I could not open that document"),
        ]

        assert opened_documents(messages) == {"/documents/a.md": THEIRS}

    def test_reopening_at_a_path_replaces_its_link(self) -> None:
        messages = [
            *opening("1", THEIRS, "a.md", "Opened 'a.docx' at /documents/a.md"),
            *opening("2", OURS, "a.md", "Opened 'b.docx' at /documents/a.md"),
        ]

        assert opened_documents(messages) == {"/documents/a.md": OURS}


IMAGE = uuid.uuid4()


@pytest.mark.asyncio
async def test_one_unreadable_copy_takes_every_file_but_the_skills() -> None:
    """The readable copy goes too: the history that said where it came from is cut,
    so it could never be checked again for whoever asks after."""

    files = {
        "/documents/theirs.md": create_file_data(f"![](draftdetective://{IMAGE})"),
        "/documents/theirs.comments.md": create_file_data("Ana: secret too"),
        "/documents/ours.md": create_file_data("ours"),
        "/notes.md": create_file_data("a summary of the secret"),
        "/skills/issues/SKILL.md": create_file_data("skill"),
        "/documents/gone.md": None,
    }
    messages = [
        *opening("1", THEIRS, "/documents/theirs.md", "Opened 'theirs.docx'"),
        *opening("2", OURS, "/documents/ours.md", "Opened 'ours.docx'"),
    ]

    async def resolve(url: str, *, token: str) -> dict[str, Any]:
        if url == THEIRS:
            raise GraphError("403")
        return {}

    drop = AsyncMock()
    with (
        patch.object(
            shared_thread_access.client, "resolve", AsyncMock(side_effect=resolve)
        ),
        patch.object(
            shared_thread_access.file_images, "drop_conversation_images", drop
        ),
    ):
        deletions, _ = await withhold_unreadable(
            {"files": files, "messages": messages}, "token", CONVERSATION
        )

    assert set(deletions) == {
        "/documents/theirs.md",
        "/documents/theirs.comments.md",
        "/documents/ours.md",
        "/notes.md",
    }
    # Or view_image would still serve it to anyone holding the reference.
    drop.assert_awaited_once_with(CONVERSATION, {IMAGE})


@pytest.mark.asyncio
async def test_when_every_copy_is_readable_nothing_changes() -> None:
    files = {
        "/documents/ours.md": create_file_data("ours"),
        "/notes.md": create_file_data("n"),
    }
    messages = opening("1", OURS, "/documents/ours.md", "Opened 'ours.docx'")

    with patch.object(
        shared_thread_access.client, "resolve", AsyncMock(return_value={})
    ):
        assert await withhold_unreadable(
            {"files": files, "messages": messages}, "t", CONVERSATION
        ) == (
            {},
            [],
        )


def test_the_history_keeps_only_what_was_said_in_the_chat() -> None:
    question = HumanMessage(content="what is it about?", id="q")
    working = opening("1", THEIRS, "/documents/a.md", "Opened 'a.docx'")
    working[0].id, working[1].id = "call", "result"
    answer = AIMessage(
        content=[
            {"type": "reasoning", "summary": [{"text": "the secret says..."}]},
            {"type": "text", "text": "An acquisition."},
        ],
        id="answer",
    )

    updates = public_history([question, *working, answer])

    assert [u.id for u in updates if isinstance(u, RemoveMessage)] == ["call", "result"]
    (kept,) = [u for u in updates if isinstance(u, AIMessage)]
    assert (kept.id, kept.content) == ("answer", "An acquisition.")
