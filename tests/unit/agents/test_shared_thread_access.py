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
    opened_links,
    public_history,
    withhold_unreadable,
)
from lib.services.microsoft.graph.client import GraphError

OURS = "https://x/ours.docx"
THEIRS = "https://x/theirs.docx"
CONVERSATION = uuid.uuid4()
SKILLS = {"/skills/issues/SKILL.md"}


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


class TestTheLinksChecked:
    def test_a_copy_replaced_at_its_path_is_still_checked(self) -> None:
        """Its reads are still in the history, though another copy holds the path."""

        messages = [
            *opening("1", THEIRS, "a.md", "Opened 'a.docx' at /documents/a.md"),
            *opening("2", OURS, "a.md", "Opened 'b.docx' at /documents/a.md"),
        ]

        assert opened_links(messages) == {THEIRS, OURS}

    def test_a_failed_open_read_nothing_to_check(self) -> None:
        messages = opening("1", THEIRS, "a.md", "I could not open that document")

        assert opened_links(messages) == set()


IMAGE = uuid.uuid4()


@pytest.mark.asyncio
async def test_one_unreadable_copy_takes_every_file_but_the_packaged_skills() -> None:
    """The readable copy goes too: the history that said where it came from is cut,
    so it could never be checked again for whoever asks after."""

    files = {
        "/documents/theirs.md": create_file_data(f"![](draftdetective://{IMAGE})"),
        "/documents/theirs.comments.md": create_file_data("Ana: secret too"),
        "/documents/ours.md": create_file_data("ours"),
        "/notes.md": create_file_data("a summary of the secret"),
        "/skills/issues/SKILL.md": create_file_data("skill"),
        "/skills/cache.md": create_file_data("the secret, kept where skills live"),
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
            {"files": files, "messages": messages}, "token", CONVERSATION, SKILLS
        )

    assert set(deletions) == {
        "/documents/theirs.md",
        "/documents/theirs.comments.md",
        "/documents/ours.md",
        "/notes.md",
        "/skills/cache.md",
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
            {"files": files, "messages": messages}, "t", CONVERSATION, SKILLS
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
