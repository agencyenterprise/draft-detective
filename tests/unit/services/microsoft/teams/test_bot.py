"""Tests for the Teams bot's authentication boundary.

The messaging endpoint is reachable by anyone who finds the URL, and the only thing
guarding it is the token the Bot Connector presents. So these are about what happens
when that token is absent or wrong.

The distinction between a refusal and a fault is load bearing rather than cosmetic:
the Bot Connector retries a 5xx and gives up on a 401, so returning 500 for a bad
token turns one bad request into a retry storm. Both of these were 500s until a
manual probe against the tunnel showed it.
"""

import json
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from jwt.algorithms import RSAAlgorithm
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
    ChannelId,
    ConversationAccount,
    ConversationReference,
    EntityTypes,
    Mention,
)
from microsoft_agents.activity.invoke_response import InvokeResponse
from microsoft_agents.hosting.core import (
    AuthenticationConstants,
    ClaimsIdentity,
    JwtTokenValidator,
)

from lib.config.env import config
from lib.services.microsoft.teams import bot


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials present, so failures cannot be blamed on configuration."""
    monkeypatch.setattr(
        config, "TEAMS_BOT_APP_ID", "11111111-2222-3333-4444-555555555555"
    )
    monkeypatch.setattr(config, "TEAMS_BOT_APP_PASSWORD", "a-secret")
    monkeypatch.setattr(
        config, "TEAMS_BOT_TENANT_ID", "66666666-7777-8888-9999-000000000000"
    )
    monkeypatch.setattr(config, "TEAMS_USER_AUTH_CONNECTION", "graph-user")
    monkeypatch.setattr(bot, "bot", bot._Bot())


class TestRefusingRequests:
    @pytest.mark.asyncio
    async def test_no_authorization_header_is_a_refusal(self, configured: None) -> None:
        with pytest.raises(PermissionError):
            await bot.bot.claims_for(None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("header", ["", "Bearer", "Basic abc", "abc", "Bearer    "])
    async def test_a_malformed_header_is_a_refusal(
        self, configured: None, header: str
    ) -> None:
        with pytest.raises(PermissionError):
            await bot.bot.claims_for(header)

    @pytest.mark.asyncio
    async def test_a_token_that_is_not_a_jwt_is_a_refusal_not_a_fault(
        self, configured: None
    ) -> None:
        """Anything other than PermissionError becomes a 500, and a 500 is retried."""

        with pytest.raises(PermissionError):
            await bot.bot.claims_for("Bearer not.a.real.jwt")

    @pytest.mark.asyncio
    async def test_missing_credentials_are_reported_as_such(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A deployment without the bot configured should say so, not 401."""

        monkeypatch.setattr(config, "TEAMS_BOT_APP_ID", None)
        monkeypatch.setattr(config, "TEAMS_BOT_APP_PASSWORD", None)
        monkeypatch.setattr(bot, "bot", bot._Bot())

        with pytest.raises(bot.NotConfigured):
            await bot.bot.claims_for("Bearer something")


class TestRequiringTheSignInConnection:
    """The bot reads only as the person who asked, so it needs a way to sign them in."""

    @pytest.mark.asyncio
    async def test_no_connection_means_the_bot_is_not_configured(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "TEAMS_USER_AUTH_CONNECTION", None)
        monkeypatch.setattr(bot, "bot", bot._Bot())

        with pytest.raises(bot.NotConfigured, match="TEAMS_USER_AUTH_CONNECTION"):
            await bot.bot.claims_for("Bearer something")


class TestBuildingTheAdapter:
    def test_the_connection_is_named_what_the_sdk_looks_up(self) -> None:
        """The SDK fetches this key by name and refuses to build without it.

        A different spelling raises "No service connection configuration provided"
        from deep inside the adapter, which surfaced as a 500 on every request.
        """

        assert bot.CONNECTION == "SERVICE_CONNECTION"

    def test_the_adapter_builds_with_credentials(self, configured: None) -> None:
        assert bot.bot.adapter is not None

    def test_the_adapter_is_reused_rather_than_rebuilt(self, configured: None) -> None:
        assert bot.bot.adapter is bot.bot.adapter


class TestPostingAFollowUp:
    """The answer arrives after the turn has ended, so ``post_later`` sends it against a
    conversation reference rather than a live context. Building that continuation
    is where the bot failed in Teams: it was round-tripped through
    model_dump/model_validate, and model_dump emits None for every unset optional
    field, which validating back rejects on all thirty of them."""

    def reference(self) -> ConversationReference:
        return bot.reference_for(
            Activity(
                type=ActivityTypes.message,
                id="1785865987930",
                channel_id=ChannelId(channel="msteams"),
                service_url="https://smba.trafficmanager.net/br/",
                conversation=ConversationAccount(id="19:abc@thread.tacv2"),
                from_property=ChannelAccount(id="29:xyz", name="Carlos Bonetti"),
                recipient=ChannelAccount(id="28:bot"),
                text="are you there?",
            )
        )

    def adapter(self, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> AsyncMock:
        process_proactive = AsyncMock(**kwargs)
        monkeypatch.setattr(
            bot.bot, "_adapter", MagicMock(process_proactive=process_proactive)
        )
        return process_proactive

    @pytest.mark.asyncio
    async def test_the_answer_lands_in_the_thread_it_came_from(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process_proactive = self.adapter(monkeypatch)

        await bot.post_later(self.reference(), "It overclaims in section 2.")

        assert process_proactive.await_args is not None
        identity, continuation, audience, deliver = process_proactive.await_args.args
        assert continuation.conversation.id == "19:abc@thread.tacv2"
        assert continuation.service_url == "https://smba.trafficmanager.net/br/"
        assert audience == bot.BOT_AUDIENCE
        # No inbound request to infer the sender from, so the claims name the bot.
        assert identity.is_authenticated
        assert identity.claims == {
            AuthenticationConstants.AUDIENCE_CLAIM: config.TEAMS_BOT_APP_ID,
            AuthenticationConstants.APP_ID_CLAIM: config.TEAMS_BOT_APP_ID,
        }

        context = MagicMock(send_activity=AsyncMock())
        await deliver(context)
        (sent,) = context.send_activity.await_args.args
        assert sent.type == ActivityTypes.message
        assert sent.text == "It overclaims in section 2."

    @pytest.mark.asyncio
    async def test_a_failure_to_post_is_logged_not_raised(
        self,
        configured: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The request was answered long ago; there is nobody to raise to."""

        self.adapter(monkeypatch, side_effect=RuntimeError("connector down"))

        with caplog.at_level(logging.ERROR, logger=bot.logger.name):
            await bot.post_later(self.reference(), "an answer")

        assert "connector down" in caplog.text

    @pytest.mark.asyncio
    async def test_missing_credentials_are_logged_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(config, "TEAMS_BOT_APP_ID", None)
        monkeypatch.setattr(bot, "bot", bot._Bot())

        with caplog.at_level(logging.ERROR, logger=bot.logger.name):
            await bot.post_later(self.reference(), "an answer")

        assert "TEAMS_BOT_APP_ID" in caplog.text


class TestShowingTyping:
    @pytest.mark.asyncio
    async def test_a_typing_indicator_that_fails_does_not_fail_the_turn(self) -> None:
        context = MagicMock(send_activity=AsyncMock(side_effect=RuntimeError("429")))

        await bot.send_typing(context)

        (sent,) = context.send_activity.await_args.args
        assert sent.type == ActivityTypes.typing


class TestReadingTheQuestion:
    """The bot's own mention is not part of the question."""

    def context(self, text: str) -> Any:
        the_bot = ChannelAccount(id="28:bot", name="Draft Detective")
        activity = Activity(
            type=ActivityTypes.message,
            text=text,
            recipient=the_bot,
            entities=[
                Mention(
                    type=EntityTypes.MENTION,
                    mentioned=the_bot,
                    text="<at>Draft Detective</at>",
                )
            ],
        )
        context = MagicMock()
        context.activity = activity
        return context

    def test_the_mention_of_the_bot_is_removed(self) -> None:
        context = self.context("<at>Draft Detective</at> does this   overclaim?")

        assert bot.question_from(context) == "does this overclaim?"

    def test_a_message_without_a_mention_is_left_as_written(self) -> None:
        """A 1:1 chat carries no mention at all."""

        context = self.context("does this overclaim?")
        context.activity.entities = []

        assert bot.question_from(context) == "does this overclaim?"


class TestFindingTheLinks:
    """A link is the only way to reach a document, so failing to spot one is fatal.

    The case that broke in Teams: the link was there, visibly, but only as a
    hyperlink -- so ``activity.text`` held the file name and the bot asked for a link
    that had already been sent.

    Every link is returned rather than the first. Which one is meant depends on what was
    asked -- "compare these two", "the second one" -- so that decision belongs to the
    agent, and picking one here would throw away the others before it could.
    """

    def message(
        self, text: str, attachments: list[Attachment] | None = None
    ) -> Activity:
        return Activity(
            type=ActivityTypes.message, text=text, attachments=attachments or []
        )

    def test_a_pasted_sharepoint_link_is_found(self) -> None:
        found = bot.document_urls_in(
            self.message(
                "have a look at "
                "https://contoso.sharepoint.com/sites/X/Shared%20Documents/a.docx"
                " please"
            )
        )
        assert len(found) == 1 and found[0].endswith("a.docx")

    def test_every_link_is_returned_in_order(self) -> None:
        """So "compare these two" is answerable, and "the second one" means something."""

        found = bot.document_urls_in(
            self.message(
                "compare https://x.sharepoint.com/sites/X/v2.docx with "
                "https://x.sharepoint.com/sites/X/v3.docx"
            )
        )

        assert found == [
            "https://x.sharepoint.com/sites/X/v2.docx",
            "https://x.sharepoint.com/sites/X/v3.docx",
        ]

    def test_the_same_link_is_not_offered_twice(self) -> None:
        """Teams repeats it: once in the text, again in the HTML, again in the card."""

        url = "https://x.sharepoint.com/sites/X/a.docx"
        activity = self.message(
            f"look at {url}",
            [Attachment(content_type="text/html", content=f'<a href="{url}">a</a>')],
        )

        assert bot.document_urls_in(activity) == [url]

    def test_trailing_punctuation_is_trimmed(self) -> None:
        """Teams decorates pasted links, and the URL must not absorb the full stop."""

        found = bot.document_urls_in(
            self.message("see https://x.sharepoint.com/sites/X/a.docx.")
        )
        assert found == ["https://x.sharepoint.com/sites/X/a.docx"]

    def test_a_message_with_no_link_finds_nothing(self) -> None:
        assert bot.document_urls_in(self.message("does this overclaim?")) == []

    def test_a_non_sharepoint_link_is_not_taken_as_a_document(self) -> None:
        assert (
            bot.document_urls_in(self.message("see https://example.com/a.docx")) == []
        )

    def test_a_link_rendered_as_a_hyperlink_is_found_in_the_html(self) -> None:
        """The reported bug. The text is the file name; the href is in an attachment."""

        activity = self.message(
            "check the abbreviations on v3-CERN for AI - cleaned.docx",
            [
                Attachment(
                    content_type="text/html",
                    content=(
                        '<div>check the abbreviations on <a href="https://contoso'
                        '.sharepoint.com/sites/Reviews/Drafts/v3-CERN.docx">'
                        "v3-CERN for AI - cleaned.docx</a></div>"
                    ),
                )
            ],
        )

        assert bot.document_urls_in(activity) == [
            "https://contoso.sharepoint.com/sites/Reviews/Drafts/v3-CERN.docx"
        ]

    def test_an_escaped_query_string_survives_the_html(self) -> None:
        """An href arrives escaped, so ``&amp;`` would truncate the link's parameters."""

        activity = self.message(
            "have a look",
            [
                Attachment(
                    content_type="text/html",
                    content=(
                        '<a href="https://x.sharepoint.com/:w:/r/sites/X/a.docx'
                        '?d=w123&amp;csf=1&amp;web=1">a.docx</a>'
                    ),
                )
            ],
        )

        found = bot.document_urls_in(activity)
        assert len(found) == 1 and found[0].endswith("?d=w123&csf=1&web=1")

    def test_a_link_in_an_unfurled_card_is_found(self) -> None:
        """Teams turns a pasted document link into a card; shape varies by card type."""

        activity = self.message(
            "v3-CERN.docx",
            [
                Attachment(
                    content_type="application/vnd.microsoft.teams.card.file.consent",
                    content={
                        "fileInfo": {
                            "contentUrl": (
                                "https://x.sharepoint.com/sites/X/DD/v3-CERN.docx"
                            )
                        }
                    },
                )
            ],
        )

        assert bot.document_urls_in(activity) == [
            "https://x.sharepoint.com/sites/X/DD/v3-CERN.docx"
        ]

    def test_a_cards_thumbnail_is_not_mistaken_for_a_document(self) -> None:
        """The preview image lives on the same host and would resolve to the wrong thing."""

        activity = self.message(
            "v3-CERN.docx",
            [
                Attachment(
                    content_type="application/vnd.microsoft.card.thumbnail",
                    content={
                        "images": [
                            {
                                "url": "https://x.sharepoint.com/sites/X/_layouts/15/"
                                "getpreview.ashx?path=/sites/X/DD/v3-CERN.docx"
                            }
                        ]
                    },
                )
            ],
        )

        assert bot.document_urls_in(activity) == []

    def test_the_visible_text_comes_first(self) -> None:
        """What someone typed is more faithful than what Teams generated around it.

        Both are offered now, so the ordering is the whole signal: the agent reads the
        list in order and the typed link leads it.
        """

        activity = self.message(
            "compare https://x.sharepoint.com/sites/X/typed.docx",
            [
                Attachment(
                    content_type="text/html",
                    content='<a href="https://x.sharepoint.com/sites/X/card.docx">x</a>',
                )
            ],
        )

        assert bot.document_urls_in(activity) == [
            "https://x.sharepoint.com/sites/X/typed.docx",
            "https://x.sharepoint.com/sites/X/card.docx",
        ]


class TestHandlingAnActivity:
    """``handle`` is the whole path from the endpoint to the turn: authenticate, parse,
    and run the given handler through the adapter, returning its invoke reply."""

    @pytest.mark.asyncio
    async def test_the_parsed_activity_and_handler_reach_the_adapter(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service_url = "https://smba.trafficmanager.net/amer/"
        claims = ClaimsIdentity(
            claims={AuthenticationConstants.SERVICE_URL_CLAIM: service_url},
            is_authenticated=True,
        )
        reply = InvokeResponse(status=200, body={"statusCode": 200})
        adapter = MagicMock()
        adapter.process_activity = AsyncMock(return_value=reply)
        monkeypatch.setattr(bot.bot, "claims_for", AsyncMock(return_value=claims))
        monkeypatch.setattr(bot.bot, "_adapter", adapter)
        on_turn = AsyncMock()

        result = await bot.handle(
            "Bearer ok",
            {
                "type": "invoke",
                "name": "adaptiveCard/action",
                "value": {},
                "serviceUrl": service_url,
            },
            on_turn,
        )

        assert result is reply
        (passed_claims, activity, handler), _ = adapter.process_activity.await_args
        assert passed_claims is claims
        assert isinstance(activity, Activity)
        assert activity.type == ActivityTypes.invoke
        assert activity.name == "adaptiveCard/action"
        assert handler is on_turn


class TestAMalformedActivity:
    """A payload this SDK will not parse must be a 4xx, for the same reason a bad
    token is: the Bot Connector retries a 5xx and gives up on a 4xx. Retrying an
    unparseable body cannot succeed, so a 500 would turn one bad -- or merely newer --
    activity into sustained load. ``Activity`` is strict enough for that to be live:
    it once rejected all thirty fields of an activity built in this codebase."""

    @pytest.mark.asyncio
    async def test_a_body_that_is_not_an_activity_is_its_own_error(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Past authentication, so the failure can only be the payload.
        monkeypatch.setattr(
            bot.bot,
            "claims_for",
            AsyncMock(return_value=ClaimsIdentity(claims={}, is_authenticated=True)),
        )

        with pytest.raises(bot.InvalidActivity):
            await bot.handle("Bearer ok", {"type": {"not": "a string"}}, AsyncMock())

    @pytest.mark.asyncio
    async def test_it_is_not_a_permission_error_or_a_bare_exception(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The route maps by type, so the type is what decides 400 over 401 or 500."""

        assert issubclass(bot.InvalidActivity, Exception)
        assert not issubclass(bot.InvalidActivity, PermissionError)
        assert not issubclass(bot.InvalidActivity, bot.NotConfigured)


def _signed(claims: dict[str, Any], key: rsa.RSAPrivateKey) -> str:
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


class TestOnlyTheBotConnectorsTokenOpensATurn:
    """The SDK's validator checks a token's signature and audience, nothing more, and
    the adapter then posts its replies -- with the bot's own token -- to whatever
    ``serviceUrl`` the activity names. Any Entra token for the bot's app id passes the
    first check: one minted by client credentials from any app registered in the bot's
    tenant, say. So these run real tokens through the real validator, with only the key
    lookup replaced, and check that a turn starts only for a token the Bot Connector
    issued for the conversation the activity says it came from: its ``serviceurl``
    claim, which the Connector puts in every token it sends, has to match."""

    SERVICE_URL = "https://smba.trafficmanager.net/amer/"

    @pytest.fixture
    def key(
        self, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> rsa.RSAPrivateKey:
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = PyJWK.from_dict(
            {
                **json.loads(RSAAlgorithm.to_jwk(private.public_key())),
                "kid": "test-key",
            }
        )
        monkeypatch.setattr(
            JwtTokenValidator._jwk_client_manager,
            "get_signing_key",
            AsyncMock(return_value=public),
        )
        return private

    @pytest.fixture
    def adapter(self, configured: None, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        adapter = MagicMock()
        adapter.process_activity = AsyncMock(return_value=None)
        bot.bot._build()
        monkeypatch.setattr(bot.bot, "_adapter", adapter)
        return adapter

    def _claims(self, **extra: Any) -> dict[str, Any]:
        now = int(time.time())
        return {
            "aud": config.TEAMS_BOT_APP_ID,
            "iat": now,
            "nbf": now,
            "exp": now + 600,
            **extra,
        }

    def _message(self, service_url: str) -> dict[str, Any]:
        return {
            "type": "message",
            "text": "what does this say?",
            "serviceUrl": service_url,
            "channelId": "msteams",
            "from": {"id": "29:someone-else"},
            "conversation": {"id": "19:channel@thread.tacv2"},
            "recipient": {"id": f"28:{config.TEAMS_BOT_APP_ID}"},
        }

    @pytest.mark.asyncio
    async def test_a_token_from_the_bot_connector_opens_a_turn(
        self, key: rsa.RSAPrivateKey, adapter: MagicMock
    ) -> None:
        token = _signed(
            self._claims(
                iss="https://api.botframework.com", serviceurl=self.SERVICE_URL
            ),
            key,
        )

        await bot.handle(
            f"Bearer {token}", self._message(self.SERVICE_URL), AsyncMock()
        )

        adapter.process_activity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_tenant_token_for_the_bots_app_id_is_refused(
        self, key: rsa.RSAPrivateKey, adapter: MagicMock
    ) -> None:
        """What client credentials from another app in the bot's tenant return."""

        tenant = config.TEAMS_BOT_TENANT_ID
        token = _signed(
            self._claims(
                iss=f"https://sts.windows.net/{tenant}/",
                tid=tenant,
                appid="99999999-8888-7777-6666-555555555555",
            ),
            key,
        )

        with pytest.raises(PermissionError):
            await bot.handle(
                f"Bearer {token}",
                self._message("https://collector.example.com/"),
                AsyncMock(),
            )
        adapter.process_activity.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_connector_token_for_another_service_url_is_refused(
        self, key: rsa.RSAPrivateKey, adapter: MagicMock
    ) -> None:
        """A genuine token does not let its holder redirect the bot's replies."""

        token = _signed(
            self._claims(
                iss="https://api.botframework.com", serviceurl=self.SERVICE_URL
            ),
            key,
        )

        with pytest.raises(PermissionError):
            await bot.handle(
                f"Bearer {token}",
                self._message("https://collector.example.com/"),
                AsyncMock(),
            )
        adapter.process_activity.assert_not_awaited()
