"""Tests for signing someone in from a channel.

The card and the invoke replies are protocol: Teams reads exact keys and content types,
and a reply it does not recognise fails silently on the client. So the shapes are pinned
here, along with the token lookup that decides between asking and answering.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientConnectionError, ClientResponseError
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    ChannelId,
    ConversationAccount,
)

from lib.services.microsoft.teams import sign_in


def card_action(**value: Any) -> Activity:
    return Activity(
        type=ActivityTypes.invoke,
        name="adaptiveCard/action",
        channel_id=ChannelId(channel="msteams"),
        from_property=ChannelAccount(id="29:asker", name="Carlos"),
        value=value,
    )


def context_for(activity: Activity, token_client: Any = None) -> MagicMock:
    context = MagicMock()
    context.activity = activity
    context.services.get.return_value = token_client
    context.send_activity = AsyncMock()
    return context


def sent_invoke_body(context: MagicMock) -> Any:
    activity = context.send_activity.await_args[0][0]
    assert activity.type == ActivityTypes.invoke_response
    # HTTP 200 always: the outcome lives in the body's statusCode.
    assert activity.value["status"] == 200
    return activity.value["body"]


class TestRecognisingTheAction:
    def test_our_verb_is_a_sign_in_action(self) -> None:
        activity = card_action(action={"verb": sign_in.VERB, "data": {"pending": "p"}})
        assert sign_in.is_sign_in_action(context_for(activity))

    @pytest.mark.parametrize(
        "activity",
        [
            card_action(action={"verb": "somethingElse"}),
            card_action(),
            Activity(type=ActivityTypes.invoke, name="signin/verifyState", value={}),
            Activity(type=ActivityTypes.message, text="hi"),
        ],
    )
    def test_anything_else_is_not(self, activity: Activity) -> None:
        assert not sign_in.is_sign_in_action(context_for(activity))

    def test_the_pending_id_and_code_are_read_from_the_action(self) -> None:
        activity = card_action(
            action={"verb": sign_in.VERB, "data": {"pending": "abc"}}, state="123456"
        )
        assert sign_in.pending_id_of(activity) == "abc"
        assert sign_in.magic_code_of(activity) == "123456"

    def test_a_first_press_carries_no_code(self) -> None:
        activity = card_action(action={"verb": sign_in.VERB, "data": {}})
        assert sign_in.pending_id_of(activity) is None
        assert sign_in.magic_code_of(activity) is None


class TestTheCard:
    def test_the_button_carries_the_pending_question(self) -> None:
        card = sign_in._card("p1", "q")
        (action,) = card["actions"]

        assert action["type"] == "Action.Execute"
        assert action["verb"] == sign_in.VERB
        assert action["data"] == {"pending": "p1"}

    def test_a_long_question_is_cut_short_on_the_card(self) -> None:
        card = sign_in._card("p1", "x" * 1000)
        assert "x" * 201 not in card["body"][1]["text"]


class TestThePendingQuestion:
    def test_it_survives_the_trip_through_storage(self) -> None:
        activity = Activity(
            type=ActivityTypes.message,
            id="1",
            channel_id=ChannelId(channel="msteams"),
            service_url="https://smba.trafficmanager.net/br/",
            conversation=ConversationAccount(id="19:x;messageid=1"),
            from_property=ChannelAccount(id="29:asker", name="Carlos"),
            recipient=ChannelAccount(id="28:bot"),
        )
        pending = sign_in.pending_from(activity, "q", "Carlos", ["https://x"])

        restored = sign_in.PendingQuestion.from_json_to_store_item(
            pending.store_item_to_json()
        )
        reference = restored.conversation_reference()

        assert restored == pending
        assert restored.asker_id == "29:asker"
        assert reference.conversation.id == "19:x;messageid=1"
        assert reference.service_url == "https://smba.trafficmanager.net/br/"


class TestLookingUpTheToken:
    @pytest.mark.asyncio
    async def test_a_token_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from lib.config.env import config

        monkeypatch.setattr(config, "TEAMS_USER_AUTH_CONNECTION", "graph-user")
        client = MagicMock()
        client.get_user_token = AsyncMock(return_value=MagicMock(token="tok"))

        token = await sign_in.user_token(
            context_for(card_action(), client), magic_code="123456"
        )

        assert token == "tok"
        kwargs = client.get_user_token.await_args.kwargs
        assert kwargs["user_id"] == "29:asker"
        assert kwargs["connection_name"] == "graph-user"
        assert kwargs["magic_code"] == "123456"

    @pytest.mark.asyncio
    async def test_no_token_is_none_not_an_error(self) -> None:
        """The token service answers "not signed in" with a 404, which the SDK raises."""

        client = MagicMock()
        client.get_user_token = AsyncMock(
            side_effect=ClientResponseError(MagicMock(), (), status=404)
        )

        assert await sign_in.user_token(context_for(card_action(), client)) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "failure",
        [
            ClientResponseError(MagicMock(), (), status=500),
            ClientConnectionError("connection refused"),
            TimeoutError(),
        ],
        ids=["an error status", "unreachable", "timed out"],
    )
    async def test_an_outage_is_its_own_failure(self, failure: Exception) -> None:
        """A token service outage must not look like "please sign in"."""

        client = MagicMock()
        client.get_user_token = AsyncMock(side_effect=failure)

        with pytest.raises(sign_in.TokenServiceUnavailable):
            await sign_in.user_token(context_for(card_action(), client))

    @pytest.mark.asyncio
    async def test_no_sign_in_link_is_an_outage_too(self) -> None:
        client = MagicMock()
        client.get_sign_in_resource = AsyncMock(
            side_effect=ClientConnectionError("connection refused")
        )
        context = context_for(card_action(), client)

        with pytest.raises(sign_in.TokenServiceUnavailable):
            await sign_in.request_sign_in(context)
        context.send_activity.assert_not_awaited()


class TestReplyingToTheAction:
    @pytest.mark.asyncio
    async def test_a_login_request_is_what_teams_reads_as_sign_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lib.config.env import config

        monkeypatch.setattr(config, "TEAMS_USER_AUTH_CONNECTION", "graph-user")
        client = MagicMock()
        client.get_sign_in_resource = AsyncMock(
            return_value=MagicMock(sign_in_link="https://token.botframework.com/x")
        )
        context = context_for(card_action(), client)

        await sign_in.request_sign_in(context)
        body = sent_invoke_body(context)

        assert body["statusCode"] == 401
        assert body["type"] == "application/vnd.microsoft.activity.loginRequest"
        assert body["value"]["connectionName"] == "graph-user"
        (button,) = body["value"]["buttons"]
        assert button["type"] == "signin"
        assert button["value"] == "https://token.botframework.com/x"

    @pytest.mark.asyncio
    async def test_signed_in_replaces_the_card(self) -> None:
        context = context_for(card_action())

        await sign_in.show_signed_in(context, answering=True)
        body = sent_invoke_body(context)

        assert body["statusCode"] == 200
        assert body["type"] == "application/vnd.microsoft.card.adaptive"
        assert "actions" not in body["value"]

    @pytest.mark.asyncio
    async def test_a_bad_code_is_reported_as_the_protocol_says(self) -> None:
        context = context_for(card_action())

        await sign_in.reject_code(context)
        body = sent_invoke_body(context)

        assert body == {
            "statusCode": 401,
            "type": "application/vnd.microsoft.error.invalidAuthCode",
        }

    @pytest.mark.asyncio
    async def test_a_notice_goes_to_the_presser_only(self) -> None:
        context = context_for(card_action())

        await sign_in.tell(context, "not yours")
        body = sent_invoke_body(context)

        assert body["type"] == "application/vnd.microsoft.activity.message"
        assert body["value"] == "not yours"
