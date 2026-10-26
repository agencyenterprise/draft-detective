"""Tests for ``on_turn``, which sends each Teams activity where it belongs."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from microsoft_agents.activity import Activity, ActivityTypes

from lib.services.microsoft.teams import conversation


class TestDispatching:
    """``on_turn`` sends each activity where it belongs, and ignores the rest."""

    def context(self, activity: Activity) -> Any:
        context = MagicMock()
        context.activity = activity
        return context

    async def dispatch(self, activity: Activity) -> tuple[AsyncMock, AsyncMock]:
        with (
            patch.object(conversation, "on_question", AsyncMock()) as question,
            patch.object(conversation, "on_sign_in_action", AsyncMock()) as sign_in,
        ):
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
