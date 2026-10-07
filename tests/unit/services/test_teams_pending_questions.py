"""Tests for the questions parked while their askers sign in.

The bug this exists for is invisible on one machine. A sign-in spans several requests --
the message that posts the Sign in card, then the card actions that follow -- and
production runs Uvicorn with ``--workers 4``, so the question has to live in Postgres
rather than in one worker's memory. What is pinned here is that each operation is the
statement it should be: a park that sweeps abandoned rows in the same transaction, and a
take that removes and returns in one statement so a question is answered once.
"""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    ChannelId,
    ConversationAccount,
)

from lib.services.microsoft.teams import pending_questions


def session_returning(value: Any, swept: int = 0) -> Any:
    """An async session whose queries yield ``value``, and report ``swept`` deletions."""

    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.rowcount = swept

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def statements(session: Any) -> list[str]:
    """Every statement the session was asked to run, lowercased."""

    return [str(call[0][0]).lower() for call in session.execute.await_args_list]


def pending() -> pending_questions.PendingQuestion:
    activity = Activity(
        type=ActivityTypes.message,
        id="1",
        channel_id=ChannelId(channel="msteams"),
        service_url="https://smba.trafficmanager.net/br/",
        conversation=ConversationAccount(id="19:x;messageid=1"),
        from_property=ChannelAccount(id="29:asker", name="Carlos"),
        recipient=ChannelAccount(id="28:bot"),
    )
    return pending_questions.pending_from(activity, "q", "Carlos", ["https://x"])


class TestThePendingQuestion:
    def test_it_survives_the_trip_through_the_table(self) -> None:
        question = pending()
        restored = pending_questions.PendingQuestion.model_validate(
            question.model_dump(mode="json")
        )
        reference = restored.conversation_reference()

        assert restored == question
        assert reference.service_url == "https://smba.trafficmanager.net/br/"

    def test_a_question_stored_by_the_previous_version_still_reads(self) -> None:
        """It also stored the asker and conversation as fields; those are ignored."""

        legacy = {
            **pending().model_dump(mode="json"),
            "asker_id": "29:asker",
            "conversation": "19:x;messageid=1",
        }

        assert pending_questions.PendingQuestion.model_validate(legacy) == pending()

    def test_the_asker_and_conversation_come_from_the_reference(self) -> None:
        """Not stored twice: the reference already names both."""

        question = pending()

        assert question.asker_id == "29:asker"
        assert question.conversation == "19:x;messageid=1"
        assert "asker_id" not in question.model_dump()


class TestParking:
    @pytest.mark.asyncio
    async def test_each_question_gets_its_own_id(self) -> None:
        with patch.object(
            pending_questions, "get_async_db_session", lambda: session_returning(None)
        ):
            first = await pending_questions.park(pending())
            second = await pending_questions.park(pending())

        assert first and second and first != second

    @pytest.mark.asyncio
    async def test_the_key_is_prefixed_like_rows_already_stored(self) -> None:
        """A card posted before a deploy carries a bare id; its row has the prefix."""

        session = session_returning(None)
        with patch.object(pending_questions, "get_async_db_session", lambda: session):
            pending_id = await pending_questions.park(pending())

        values = session.execute.await_args_list[0][0][0].compile().params
        assert values["key"] == f"pending-question/{pending_id}"

    @pytest.mark.asyncio
    async def test_a_park_also_sweeps_abandoned_rows_in_one_transaction(self) -> None:
        """Abandoned rows hold the question -- its text and its sender."""

        session = session_returning(None)
        with patch.object(pending_questions, "get_async_db_session", lambda: session):
            await pending_questions.park(pending())

        ran = statements(session)
        assert ran[0].startswith("insert")
        sweep = next(s for s in ran if s.startswith("delete"))
        assert "updated_at" in sweep, "a sweep on an unindexed column scans the table"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_sweep_that_removed_rows_says_so(self) -> None:
        session = session_returning(None, swept=3)
        with (
            patch.object(pending_questions, "get_async_db_session", lambda: session),
            patch.object(pending_questions.logger, "info") as logged,
        ):
            await pending_questions.park(pending())

        assert logged.call_args[0][1] == 3

    def test_the_window_is_generous_next_to_a_sign_in(self) -> None:
        """A sign-in takes about a minute, so an hour cannot cut one short."""

        assert pending_questions.ABANDONED_AFTER >= timedelta(minutes=30)
        assert pending_questions.ABANDONED_AFTER <= timedelta(days=1)


class TestTakingItBack:
    @pytest.mark.asyncio
    async def test_a_missing_question_is_none(self) -> None:
        with patch.object(
            pending_questions, "get_async_db_session", lambda: session_returning(None)
        ):
            assert await pending_questions.peek("gone") is None
            assert await pending_questions.take("gone") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("lookup", ["peek", "take"])
    async def test_lookups_use_the_prefixed_key(self, lookup: str) -> None:
        session = session_returning(None)
        with patch.object(pending_questions, "get_async_db_session", lambda: session):
            await getattr(pending_questions, lookup)("abc")

        params = session.execute.await_args_list[0][0][0].compile().params
        assert "pending-question/abc" in params.values()

    @pytest.mark.asyncio
    async def test_peek_leaves_it_in_place(self) -> None:
        session = session_returning(pending().model_dump(mode="json"))
        with patch.object(pending_questions, "get_async_db_session", lambda: session):
            found = await pending_questions.peek("p1")

        assert found == pending()
        assert statements(session)[0].startswith("select")

    @pytest.mark.asyncio
    async def test_take_removes_and_returns_in_one_statement(self) -> None:
        """A read then a delete would let two presses both answer the question."""

        session = session_returning(pending().model_dump(mode="json"))
        with patch.object(pending_questions, "get_async_db_session", lambda: session):
            taken = await pending_questions.take("p1")

        (statement,) = statements(session)
        assert statement.startswith("delete") and "returning" in statement
        assert taken == pending()
        session.commit.assert_awaited_once()
