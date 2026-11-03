"""Tests for the add-in chat's suggestions.

The agent hears once what became of each suggestion, worded from what was stored.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.microsoft.word import chat_suggestions, handoffs
from lib.services.microsoft.word.chat_suggestions import ChatSuggestion, news
from lib.services.microsoft.word.handoffs import (
    Account,
    HandoffComment,
    HandoffEdit,
    HandoffItems,
    HandoffOutcome,
    ItemOutcome,
)

ANA = Account(oid="oid-ana", tid="tid-contoso")
PATH_URL = "https://contoso.sharepoint.com/sites/Policy/Shared%20Documents/Draft.docx"
NOW = datetime.now(UTC)
ITEMS = HandoffItems(
    comments=[HandoffComment(quote="is the only option", comment="Overclaims.")],
    edits=[HandoffEdit(quote="recieve", replacement="receive")],
)


def suggestion(
    status: str,
    finished: datetime | None = None,
    outcome: HandoffOutcome | None = None,
    heard: datetime | None = None,
) -> ChatSuggestion:
    return ChatSuggestion(
        id=uuid.uuid4(),
        status=status,  # type: ignore[arg-type]  # the four statuses, as plain strings
        document_name="Draft.docx",
        document_url=PATH_URL,
        items=ITEMS,
        outcome=outcome,
        created_at=NOW - timedelta(hours=1),
        finished_at=finished,
        heard_at=heard,
    )


class TestWhatTheAgentHears:
    def test_an_application_since_the_last_turn_is_described(self) -> None:
        outcome = HandoffOutcome(
            items=[
                ItemOutcome(kind="comment", quote="is the only option", applied=True),
                ItemOutcome(
                    kind="edit",
                    quote="recieve",
                    applied=False,
                    detail=handoffs.REASONS["not_found"],
                ),
            ]
        )
        said = news([suggestion("applied", NOW, outcome)])

        assert "1 of 2" in said
        assert "recieve" in said and handoffs.REASONS["not_found"] in said

    def test_a_dismissal_is_described(self) -> None:
        said = news([suggestion("dismissed", NOW)])

        assert "dismissed" in said and "none were applied" in said

    def test_what_it_was_told_is_not_told_again(self) -> None:
        """By ``ask_to_apply`` while it waited, or as news before: once is enough.

        Told by when it heard, not by when the last turn began, so a card that settled
        while the answer waited on another one is still news.
        """

        heard = suggestion("applied", NOW - timedelta(minutes=10), heard=NOW)
        not_yet = suggestion("dismissed", NOW - timedelta(minutes=10))

        said = news([heard, not_yet])

        assert "dismissed" in said and "1 of" not in said

    def test_ones_still_waiting_are_mentioned(self) -> None:
        said = news([suggestion("pending")])

        assert "1 set(s)" in said and "still waiting" in said

    def test_nothing_to_say_says_nothing(self) -> None:
        assert news([]) == ""


class TestReplacingACardsItems:
    @pytest.mark.asyncio
    async def test_only_a_pending_card_of_theirs_is_changed(self) -> None:
        result = MagicMock()
        result.first.return_value = None
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        with patch.object(
            chat_suggestions, "get_async_db_session", return_value=session
        ):
            changed = await chat_suggestions.replace_items(uuid.uuid4(), ANA, ITEMS)

        assert changed is False
        sql = str(session.execute.await_args.args[0]).lower()
        assert sql.startswith("update microsoft_word_handoffs")
        assert "status =" in sql and "requested_by_oid" in sql
        assert "chat_thread_id is not null" in sql and "created_at >=" in sql
