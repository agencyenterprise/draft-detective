"""Tests for what the Teams bot does with each activity.

What is worth pinning first is the answer that arrives *after* the turn has ended. The
person has already been told "I will follow up here shortly", so a failure that is
merely logged leaves them waiting forever -- and a detached task whose result is never
read does not even reliably log. That combination is how a lost reply becomes silent.

Then the sign-in flow: whose parked question a card press may release, when the bot
asks Teams to sign someone in, and what a token-service outage looks like to the person.
"""

import asyncio
import logging
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

from lib.services.microsoft.teams import conversation
from lib.services.microsoft.teams.pending_questions import PendingQuestion


class TestWhenAnsweringFails:
    """Every way out of ``_answer_into_thread`` has to end in something being said."""

    @pytest.mark.asyncio
    async def test_a_reported_failure_is_apologised_for(self) -> None:
        failed = AsyncMock(
            return_value=type("Answer", (), {"failed": True, "error": "boom", "text": ""})()
        )
        posted = AsyncMock()
        with patch.object(conversation, "answer_question", failed), patch.object(
            conversation.bot, "post_later", posted
        ):
            await conversation._answer_into_thread(
                "ref", "does this overclaim?", "Carlos", "19:x", [], "token"
            )

        posted.assert_awaited_once()
        assert posted.await_args is not None
        assert posted.await_args[0][1] == conversation.APOLOGY

    @pytest.mark.asyncio
    async def test_a_raise_is_apologised_for_too(self) -> None:
        """``answer_question`` reports rather than raises, so this is the gap past it.

        Its own guard does not cover prompt formatting or the run config, and an
        ``except Exception`` never covers a future edit.
        """

        posted = AsyncMock()
        with patch.object(
            conversation, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(conversation.bot, "post_later", posted):
            await conversation._answer_into_thread(
                "ref", "does this overclaim?", "Carlos", "19:x", [], "token"
            )

        posted.assert_awaited_once()
        assert posted.await_args is not None
        assert posted.await_args[0][1] == conversation.APOLOGY

    @pytest.mark.asyncio
    async def test_a_raise_does_not_escape_to_the_task(self) -> None:
        """Because the caller is detached, an escape would only be a warning."""

        with patch.object(
            conversation, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(conversation.bot, "post_later", AsyncMock()):
            await conversation._answer_into_thread("ref", "q", "Carlos", "19:x", [], "t")

    @pytest.mark.asyncio
    async def test_the_question_is_truncated_in_the_log(self) -> None:
        """A question can quote the document, and these are confidential."""

        question = "x" * 500
        with patch.object(
            conversation, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(conversation.bot, "post_later", AsyncMock()), patch.object(
            conversation.logger, "exception"
        ) as logged:
            await conversation._answer_into_thread("ref", question, "C", "19:x", [], "t")

        assert logged.call_args is not None
        assert len(logged.call_args[0][1]) == 120


class TestRetiringADetachedTask:
    """``_finished`` is the backstop for anything the coroutine's own guard misses."""

    async def _task(self, coroutine: Any) -> "asyncio.Task[None]":
        task = asyncio.create_task(coroutine)
        conversation._running.add(task)
        task.add_done_callback(conversation._finished)
        await asyncio.sleep(0)
        return task

    @pytest.mark.asyncio
    async def test_a_completed_task_is_released(self) -> None:
        """Otherwise the set grows for the life of the process."""

        async def fine() -> None:
            return None

        task = await self._task(fine())
        await task
        await asyncio.sleep(0)
        assert task not in conversation._running

    @pytest.mark.asyncio
    async def test_a_failure_is_logged_rather_than_left_unretrieved(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The bug this replaced: ``add_done_callback(_running.discard)`` alone.

        It dropped the reference without reading the result, so asyncio had an
        exception nobody retrieved -- a shutdown warning at best.
        """

        async def broken() -> None:
            raise RuntimeError("something outside the guard")

        with caplog.at_level(logging.ERROR, logger=conversation.logger.name):
            task = await self._task(broken())
            with pytest.raises(RuntimeError):
                await task
            await asyncio.sleep(0)

        assert "detached answer task failed" in caplog.text
        assert "something outside the guard" in caplog.text
        assert task not in conversation._running

    @pytest.mark.asyncio
    async def test_cancellation_is_not_reported_as_a_fault(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Shutdown cancels in-flight work; that is not an error worth paging over."""

        async def slow() -> None:
            await asyncio.sleep(10)

        with caplog.at_level(logging.ERROR, logger=conversation.logger.name):
            task = await self._task(slow())
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0)

        assert "failed" not in caplog.text
        assert task not in conversation._running


class TestSigningInFromTheCard:
    """``on_sign_in_action``: whose question is released, and when.

    Anyone in a channel can press the card's button, and the answer has to be read
    with the asker's access -- so only the asker's press may release the question.
    """

    def pending(self) -> Any:
        return PendingQuestion(
            question="what does it claim?",
            author="Carlos",
            document_urls=["https://carlosbonetti.sharepoint.com/sites/x/doc.docx"],
            reference={
                "conversation": {"id": "19:x;messageid=1"},
                "user": {"id": "29:asker"},
                "serviceUrl": "https://smba.trafficmanager.net/br/",
            },
        )

    def context(self, presser: str = "29:asker", state: str | None = None) -> Any:


        value: dict[str, Any] = {
            "action": {"verb": conversation.sign_in.VERB, "data": {"pending": "p1"}}
        }
        if state:
            value["state"] = state
        context = MagicMock()
        context.activity = Activity(
            type=ActivityTypes.invoke,
            name="adaptiveCard/action",
            from_property=ChannelAccount(id=presser, name="someone"),
            value=value,
        )
        return context

    def patched(
        self,
        token: str | None,
        pending: Any,
        token_error: Exception | None = None,
        link_error: Exception | None = None,
        tokens: list[str | None] | None = None,
    ) -> dict[str, Any]:
        sign_in = conversation.sign_in
        pending_store = conversation.pending_questions
        return {
            "peek": patch.object(pending_store, "peek", AsyncMock(return_value=pending)),
            "take": patch.object(pending_store, "take", AsyncMock(return_value=pending)),
            "user_token": patch.object(
                sign_in,
                "user_token",
                AsyncMock(return_value=token, side_effect=token_error or tokens),
            ),
            "request_sign_in": patch.object(
                sign_in, "request_sign_in", AsyncMock(side_effect=link_error)
            ),
            "show_signed_in": patch.object(sign_in, "show_signed_in", AsyncMock()),
            "reject_code": patch.object(sign_in, "reject_code", AsyncMock()),
            "tell": patch.object(sign_in, "tell", AsyncMock()),
            "answer": patch.object(conversation, "_start_answering"),
        }

    async def run(
        self, context: Any, token: str | None, pending: Any, **extra: Any
    ) -> dict[str, Any]:
        patches = self.patched(token, pending, **extra)
        mocks = {name: p.start() for name, p in patches.items()}
        try:
            await conversation.on_sign_in_action(context)
        finally:
            for p in patches.values():
                p.stop()
        return mocks

    @pytest.mark.asyncio
    async def test_someone_else_pressing_is_told_and_nothing_is_read(self) -> None:
        mocks = await self.run(self.context(presser="29:other"), "tok", self.pending())

        mocks["tell"].assert_awaited_once()
        mocks["user_token"].assert_not_awaited()
        mocks["take"].assert_not_awaited()
        mocks["answer"].assert_not_called()

    @pytest.mark.asyncio
    async def test_no_token_yet_asks_teams_to_sign_them_in(self) -> None:
        mocks = await self.run(self.context(), None, self.pending())

        mocks["request_sign_in"].assert_awaited_once()
        mocks["take"].assert_not_awaited()
        mocks["answer"].assert_not_called()

    @pytest.mark.asyncio
    async def test_the_code_from_teams_is_redeemed(self) -> None:
        mocks = await self.run(self.context(state="123456"), "tok", self.pending())

        assert mocks["user_token"].await_args.kwargs["magic_code"] == "123456"

    @pytest.mark.asyncio
    async def test_once_signed_in_the_question_is_answered_with_their_token(
        self,
    ) -> None:
        pending = self.pending()
        mocks = await self.run(self.context(state="123456"), "tok", pending)

        mocks["take"].assert_awaited_once_with("p1")
        mocks["show_signed_in"].assert_awaited_once()
        assert mocks["show_signed_in"].await_args.kwargs["answering"] is True
        args = mocks["answer"].call_args[0]
        assert args[1:] == (
            pending.question,
            pending.author,
            pending.conversation,
            pending.document_urls,
            "tok",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("where", ["token_error", "link_error"])
    async def test_a_token_service_outage_is_told_to_the_presser(
        self, where: str
    ) -> None:
        """Whether the token lookup or the sign-in link fails, the card gets an answer."""

        outage = conversation.sign_in.TokenServiceUnavailable("down")
        mocks = await self.run(self.context(), None, self.pending(), **{where: outage})

        mocks["tell"].assert_awaited_once()
        assert mocks["tell"].await_args[0][1] == conversation.SIGN_IN_UNAVAILABLE
        mocks["take"].assert_not_awaited()
        mocks["answer"].assert_not_called()

    @pytest.mark.asyncio
    async def test_a_code_that_does_not_redeem_is_rejected(self) -> None:
        """Teams is told the code was bad, rather than asked to start over."""

        mocks = await self.run(
            self.context(state="123456"), None, self.pending(), tokens=[None, None]
        )

        mocks["reject_code"].assert_awaited_once()
        mocks["request_sign_in"].assert_not_awaited()
        mocks["take"].assert_not_awaited()
        mocks["answer"].assert_not_called()

    @pytest.mark.asyncio
    async def test_a_code_already_redeemed_still_counts_as_signed_in(self) -> None:
        """A repeated delivery carries a used code; the token from the first one stands."""

        mocks = await self.run(
            self.context(state="123456"), None, self.pending(), tokens=[None, "tok"]
        )

        mocks["reject_code"].assert_not_awaited()
        mocks["take"].assert_awaited_once_with("p1")
        assert mocks["answer"].call_args[0][-1] == "tok"

    @pytest.mark.asyncio
    async def test_no_code_and_no_token_starts_a_sign_in(self) -> None:
        mocks = await self.run(self.context(), None, self.pending())

        mocks["request_sign_in"].assert_awaited_once()
        mocks["reject_code"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_question_already_answered_is_not_answered_again(self) -> None:
        """Teams can deliver the action twice; ``take`` hands the question out once."""

        mocks = await self.run(self.context(), "tok", None)

        assert mocks["show_signed_in"].await_args.kwargs["answering"] is False
        mocks["answer"].assert_not_called()


class TestAskingBeforeAnswering:
    """A question from someone not signed in is parked until they sign in."""

    def context(self) -> Any:


        context = MagicMock()
        context.activity = Activity(
            type=ActivityTypes.message,
            text="what does it claim?",
            channel_id=ChannelId(channel="msteams"),
            service_url="https://smba.trafficmanager.net/br/",
            conversation=ConversationAccount(id="19:x"),
            from_property=ChannelAccount(id="29:asker", name="Carlos"),
            recipient=ChannelAccount(id="28:bot"),
        )
        context.send_activity = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_no_token_parks_the_question_and_asks(self) -> None:
        with patch.object(
            conversation.sign_in, "user_token", AsyncMock(return_value=None)
        ), patch.object(
            conversation.pending_questions, "park", AsyncMock(return_value="p1")
        ) as park, patch.object(
            conversation.sign_in, "ask_to_sign_in", AsyncMock()
        ) as ask, patch.object(conversation, "_start_answering") as answer:
            await conversation.on_question(self.context())

        park.assert_awaited_once()
        ask.assert_awaited_once()
        answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_token_service_outage_is_said_not_raised(self) -> None:
        """A 5xx would only be retried by the Connector, and nobody would hear why."""

        with patch.object(
            conversation.sign_in,
            "user_token",
            AsyncMock(side_effect=conversation.sign_in.TokenServiceUnavailable("down")),
        ), patch.object(conversation.pending_questions, "park", AsyncMock()) as park, patch.object(
            conversation, "_start_answering"
        ) as answer:
            context = self.context()
            await conversation.on_question(context)

        context.send_activity.assert_awaited_once_with(conversation.SIGN_IN_UNAVAILABLE)
        park.assert_not_awaited()
        answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_signed_in_asker_is_answered_straight_away(self) -> None:
        with patch.object(
            conversation.sign_in, "user_token", AsyncMock(return_value="tok")
        ), patch.object(conversation.pending_questions, "park", AsyncMock()) as park, patch.object(
            conversation.bot, "send_typing", AsyncMock()
        ), patch.object(conversation, "_start_answering") as answer:
            await conversation.on_question(self.context())

        park.assert_not_awaited()
        assert answer.call_args[0][-1] == "tok"


class TestDispatching:
    """``on_turn`` sends each activity where it belongs, and ignores the rest."""

    def context(self, activity: Activity) -> Any:
        context = MagicMock()
        context.activity = activity
        return context

    async def dispatch(self, activity: Activity) -> tuple[AsyncMock, AsyncMock]:
        with patch.object(conversation, "on_question", AsyncMock()) as question, patch.object(
            conversation, "on_sign_in_action", AsyncMock()
        ) as sign_in:
            await conversation.on_turn(self.context(activity))
        return question, sign_in

    @pytest.mark.asyncio
    async def test_a_message_is_a_question(self) -> None:
        question, sign_in = await self.dispatch(
            Activity(type=ActivityTypes.message, text="hi")
        )

        question.assert_awaited_once()
        sign_in.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_sign_in_cards_action_signs_in(self) -> None:
        question, sign_in = await self.dispatch(
            Activity(
                type=ActivityTypes.invoke,
                name="adaptiveCard/action",
                value={"action": {"verb": conversation.sign_in.VERB}},
            )
        )

        sign_in.assert_awaited_once()
        question.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "activity",
        [
            Activity(type=ActivityTypes.conversation_update),
            Activity(type=ActivityTypes.typing),
            Activity(type=ActivityTypes.invoke, name="signin/verifyState", value={}),
        ],
        ids=["membership change", "typing", "an old sign-in card"],
    )
    async def test_anything_else_is_ignored(self, activity: Activity) -> None:
        question, sign_in = await self.dispatch(activity)

        question.assert_not_awaited()
        sign_in.assert_not_awaited()
