"""Tests for the Teams messaging endpoint's own logic.

What is worth pinning here is the answer that arrives *after* the turn has ended. The
person has already been told "I will follow up here shortly", so a failure that is
merely logged leaves them waiting forever -- and a detached task whose result is never
read does not even reliably log. That combination is how a lost reply becomes silent.

The endpoint's authentication boundary is covered in ``test_teams_bot.py``, where the
token validation lives.
"""

import asyncio
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lib.api.routers.microsoft import teams


class TestWhenAnsweringFails:
    """Every way out of ``_answer_into_thread`` has to end in something being said."""

    @pytest.mark.asyncio
    async def test_a_reported_failure_is_apologised_for(self) -> None:
        failed = AsyncMock(
            return_value=type("Answer", (), {"failed": True, "error": "boom", "text": ""})()
        )
        posted = AsyncMock()
        with patch.object(teams, "answer_question", failed), patch.object(
            teams.bot, "post_later", posted
        ):
            await teams._answer_into_thread(
                "ref", "does this overclaim?", "Carlos", "19:x", [], "token"
            )

        posted.assert_awaited_once()
        assert posted.await_args is not None
        assert posted.await_args[0][1] == teams.APOLOGY

    @pytest.mark.asyncio
    async def test_a_raise_is_apologised_for_too(self) -> None:
        """``answer_question`` reports rather than raises, so this is the gap past it.

        Its own guard does not cover prompt formatting or the run config, and an
        ``except Exception`` never covers a future edit.
        """

        posted = AsyncMock()
        with patch.object(
            teams, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(teams.bot, "post_later", posted):
            await teams._answer_into_thread(
                "ref", "does this overclaim?", "Carlos", "19:x", [], "token"
            )

        posted.assert_awaited_once()
        assert posted.await_args is not None
        assert posted.await_args[0][1] == teams.APOLOGY

    @pytest.mark.asyncio
    async def test_a_raise_does_not_escape_to_the_task(self) -> None:
        """Because the caller is detached, an escape would only be a warning."""

        with patch.object(
            teams, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(teams.bot, "post_later", AsyncMock()):
            await teams._answer_into_thread("ref", "q", "Carlos", "19:x", [], "t")

    @pytest.mark.asyncio
    async def test_the_question_is_truncated_in_the_log(self) -> None:
        """A question can quote the document, and these are confidential."""

        question = "x" * 500
        with patch.object(
            teams, "answer_question", AsyncMock(side_effect=RuntimeError("upstream"))
        ), patch.object(teams.bot, "post_later", AsyncMock()), patch.object(
            teams.logger, "exception"
        ) as logged:
            await teams._answer_into_thread("ref", question, "C", "19:x", [], "t")

        assert logged.call_args is not None
        assert len(logged.call_args[0][1]) == 120


class TestRetiringADetachedTask:
    """``_finished`` is the backstop for anything the coroutine's own guard misses."""

    async def _task(self, coroutine: Any) -> "asyncio.Task[None]":
        task = asyncio.create_task(coroutine)
        teams._running.add(task)
        task.add_done_callback(teams._finished)
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
        assert task not in teams._running

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

        with caplog.at_level(logging.ERROR, logger=teams.logger.name):
            task = await self._task(broken())
            with pytest.raises(RuntimeError):
                await task
            await asyncio.sleep(0)

        assert "detached answer task failed" in caplog.text
        assert "something outside the guard" in caplog.text
        assert task not in teams._running

    @pytest.mark.asyncio
    async def test_cancellation_is_not_reported_as_a_fault(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Shutdown cancels in-flight work; that is not an error worth paging over."""

        async def slow() -> None:
            await asyncio.sleep(10)

        with caplog.at_level(logging.ERROR, logger=teams.logger.name):
            task = await self._task(slow())
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0)

        assert "failed" not in caplog.text
        assert task not in teams._running


class TestAnsweringAnInvoke:
    """The sign-in card's invoke reply is protocol, not a formality.

    Teams reads the body to decide whether to open the sign-in window or replace the
    card, so the endpoint passes the turn's reply through rather than an empty 200.
    """

    LOGIN_REQUEST = {
        "statusCode": 401,
        "type": "application/vnd.microsoft.activity.loginRequest",
        "value": {"connectionName": "graph-user", "buttons": []},
    }

    def response_for(self, status: int, body: Any) -> Any:
        from microsoft_agents.activity.invoke_response import InvokeResponse

        return InvokeResponse(status=status, body=body)

    def test_the_body_reaches_teams_unchanged(self) -> None:
        response = teams._invoke_response(self.response_for(200, self.LOGIN_REQUEST))

        assert response.status_code == 200
        assert response.media_type == "application/json"
        assert json.loads(response.body) == self.LOGIN_REQUEST

    def test_no_body_keeps_its_status(self) -> None:
        """An invoke no route handled comes back 501 with nothing to send."""

        response = teams._invoke_response(self.response_for(501, None))

        assert response.status_code == 501
        assert not response.body

    def client(self) -> Any:
        """Just this router, not the whole application.

        Importing ``lib.api.main`` here builds every route and reads module-level
        config, which made this test depend on which other test had run first.
        """

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(teams.router, prefix="/api/microsoft")
        return TestClient(app, raise_server_exceptions=False)

    def test_an_ordinary_message_still_gets_an_empty_200(self) -> None:
        """The Connector treats a body on a normal activity as a payload."""

        with patch.object(teams.bot, "handle", AsyncMock(return_value=None)):
            result = self.client().post(
                "/api/microsoft/teams/messages",
                json={"type": "message", "text": "hi", "conversation": {"id": "19:x"}},
                headers={"Authorization": "Bearer ok"},
            )

        assert result.status_code == 200
        assert result.content == b""

    def test_an_invoke_reply_reaches_the_channel_over_http(self) -> None:
        """End to end through the route, since the reply is the whole point."""

        with patch.object(
            teams.bot,
            "handle",
            AsyncMock(return_value=self.response_for(200, self.LOGIN_REQUEST)),
        ):
            result = self.client().post(
                "/api/microsoft/teams/messages",
                json={"type": "invoke", "name": "adaptiveCard/action"},
                headers={"Authorization": "Bearer ok"},
            )

        assert result.status_code == 200
        assert result.json() == self.LOGIN_REQUEST


class TestSigningInFromTheCard:
    """``_on_sign_in_action``: whose question is released, and when.

    Anyone in a channel can press the card's button, and the answer has to be read
    with the asker's access -- so only the asker's press may release the question.
    """

    def pending(self) -> Any:
        from lib.services.microsoft.teams.sign_in import PendingQuestion

        return PendingQuestion(
            question="what does it claim?",
            author="Carlos",
            asker_id="29:asker",
            conversation="19:x;messageid=1",
            document_urls=["https://carlosbonetti.sharepoint.com/sites/x/doc.docx"],
            reference={"conversation": {"id": "19:x;messageid=1"}},
        )

    def context(self, presser: str = "29:asker", state: str | None = None) -> Any:
        from unittest.mock import MagicMock

        from microsoft_agents.activity import Activity, ActivityTypes, ChannelAccount

        value: dict[str, Any] = {
            "action": {"verb": teams.sign_in.VERB, "data": {"pending": "p1"}}
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
    ) -> dict[str, Any]:
        sign_in = teams.sign_in
        return {
            "peek": patch.object(sign_in, "peek", AsyncMock(return_value=pending)),
            "take": patch.object(sign_in, "take", AsyncMock(return_value=pending)),
            "user_token": patch.object(
                sign_in,
                "user_token",
                AsyncMock(return_value=token, side_effect=token_error),
            ),
            "request_sign_in": patch.object(
                sign_in, "request_sign_in", AsyncMock(side_effect=link_error)
            ),
            "show_signed_in": patch.object(sign_in, "show_signed_in", AsyncMock()),
            "tell": patch.object(sign_in, "tell", AsyncMock()),
            "answer": patch.object(teams, "_start_answering"),
        }

    async def run(
        self, context: Any, token: str | None, pending: Any, **errors: Exception
    ) -> dict[str, Any]:
        patches = self.patched(token, pending, **errors)
        mocks = {name: p.start() for name, p in patches.items()}
        try:
            await teams._on_sign_in_action(context, None)
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

        outage = teams.sign_in.TokenServiceUnavailable("down")
        mocks = await self.run(self.context(), None, self.pending(), **{where: outage})

        mocks["tell"].assert_awaited_once()
        assert mocks["tell"].await_args[0][1] == teams.SIGN_IN_UNAVAILABLE
        mocks["take"].assert_not_awaited()
        mocks["answer"].assert_not_called()

    @pytest.mark.asyncio
    async def test_a_question_already_answered_is_not_answered_again(self) -> None:
        """Teams can deliver the action twice; ``take`` hands the question out once."""

        mocks = await self.run(self.context(), "tok", None)

        assert mocks["show_signed_in"].await_args.kwargs["answering"] is False
        mocks["answer"].assert_not_called()


class TestAskingBeforeAnswering:
    """A question from someone not signed in is parked until they sign in."""

    def context(self) -> Any:
        from unittest.mock import MagicMock

        from microsoft_agents.activity import (
            Activity,
            ActivityTypes,
            ChannelAccount,
            ChannelId,
            ConversationAccount,
        )

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
            teams.sign_in, "user_token", AsyncMock(return_value=None)
        ), patch.object(
            teams.sign_in, "park", AsyncMock(return_value="p1")
        ) as park, patch.object(
            teams.sign_in, "ask_to_sign_in", AsyncMock()
        ) as ask, patch.object(teams, "_start_answering") as answer:
            await teams._on_question(self.context(), None)

        park.assert_awaited_once()
        ask.assert_awaited_once()
        answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_token_service_outage_is_said_not_raised(self) -> None:
        """A 5xx would only be retried by the Connector, and nobody would hear why."""

        with patch.object(
            teams.sign_in,
            "user_token",
            AsyncMock(side_effect=teams.sign_in.TokenServiceUnavailable("down")),
        ), patch.object(teams.sign_in, "park", AsyncMock()) as park, patch.object(
            teams, "_start_answering"
        ) as answer:
            context = self.context()
            await teams._on_question(context, None)

        context.send_activity.assert_awaited_once_with(teams.SIGN_IN_UNAVAILABLE)
        park.assert_not_awaited()
        answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_signed_in_asker_is_answered_straight_away(self) -> None:
        with patch.object(
            teams.sign_in, "user_token", AsyncMock(return_value="tok")
        ), patch.object(teams.sign_in, "park", AsyncMock()) as park, patch.object(
            teams.bot, "send_typing", AsyncMock()
        ), patch.object(teams, "_start_answering") as answer:
            await teams._on_question(self.context(), None)

        park.assert_not_awaited()
        assert answer.call_args[0][-1] == "tok"
