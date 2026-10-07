"""Tests for the answer that arrives after a Teams turn has ended.

The person has already been told "I will follow up here shortly", so a failure that is
merely logged leaves them waiting forever -- and a detached task whose result is never
read does not even reliably log. That combination is how a lost reply becomes silent.
"""

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from lib.services.microsoft.teams import conversation


class TestWhenAnsweringFails:
    """Every way out of ``_answer_into_thread`` has to end in something being said."""

    @pytest.mark.asyncio
    async def test_a_reported_failure_is_apologised_for(self) -> None:
        failed = AsyncMock(
            return_value=type(
                "Answer", (), {"failed": True, "error": "boom", "text": ""}
            )()
        )
        posted = AsyncMock()
        with (
            patch.object(conversation, "answer_question", failed),
            patch.object(conversation.bot, "post_later", posted),
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
        with (
            patch.object(
                conversation,
                "answer_question",
                AsyncMock(side_effect=RuntimeError("upstream")),
            ),
            patch.object(conversation.bot, "post_later", posted),
        ):
            await conversation._answer_into_thread(
                "ref", "does this overclaim?", "Carlos", "19:x", [], "token"
            )

        posted.assert_awaited_once()
        assert posted.await_args is not None
        assert posted.await_args[0][1] == conversation.APOLOGY

    @pytest.mark.asyncio
    async def test_a_raise_does_not_escape_to_the_task(self) -> None:
        """Because the caller is detached, an escape would only be a warning."""

        with (
            patch.object(
                conversation,
                "answer_question",
                AsyncMock(side_effect=RuntimeError("upstream")),
            ),
            patch.object(conversation.bot, "post_later", AsyncMock()),
        ):
            await conversation._answer_into_thread(
                "ref", "q", "Carlos", "19:x", [], "t"
            )

    @pytest.mark.asyncio
    async def test_the_question_is_truncated_in_the_log(self) -> None:
        """A question can quote the document, and these are confidential."""

        question = "x" * 500
        with (
            patch.object(
                conversation,
                "answer_question",
                AsyncMock(side_effect=RuntimeError("upstream")),
            ),
            patch.object(conversation.bot, "post_later", AsyncMock()),
            patch.object(conversation.logger, "exception") as logged,
        ):
            await conversation._answer_into_thread(
                "ref", question, "C", "19:x", [], "t"
            )

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
