"""Tests for the Teams bot's authentication boundary.

The messaging endpoint is reachable by anyone who finds the URL, and the only thing
guarding it is the token the Bot Connector presents. So these are about what happens
when that token is absent or wrong.

The distinction between a refusal and a fault is load bearing rather than cosmetic:
the Bot Connector retries a 5xx and gives up on a 401, so returning 500 for a bad
token turns one bad request into a retry storm. Both of these were 500s until a
manual probe against the tunnel showed it.
"""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from microsoft_agents.activity import (
    Activity,
    ActivityTypes,
    Attachment,
    ChannelAccount,
    EntityTypes,
    Mention,
)
from microsoft_agents.activity.invoke_response import InvokeResponse
from microsoft_agents.hosting.core import ClaimsIdentity

from lib.services.microsoft.teams import bot


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials present, so failures cannot be blamed on configuration."""

    from lib.config.env import config

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

        from lib.config.env import config

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
        from lib.config.env import config

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


class TestTheFollowUpActivity:
    """The answer arrives after the turn has ended, so it is sent against a
    conversation reference rather than a live context. Building that continuation
    is where the bot failed in Teams: it was round-tripped through
    model_dump/model_validate, and model_dump emits None for every unset optional
    field, which validating back rejects on all thirty of them."""

    def incoming(self):
        from microsoft_agents.activity import (
            Activity,
            ActivityTypes,
            ChannelAccount,
            ConversationAccount,
        )

        return Activity(
            type=ActivityTypes.message,
            id="1785865987930",
            channel_id="msteams",
            service_url="https://smba.trafficmanager.net/br/",
            conversation=ConversationAccount(id="19:abc@thread.tacv2"),
            from_property=ChannelAccount(id="29:xyz", name="Carlos Bonetti"),
            recipient=ChannelAccount(id="28:bot"),
            text="are you there?",
        )

    def test_the_continuation_keeps_where_to_send(self) -> None:
        from microsoft_agents.activity import Activity, ActivityTypes
        from microsoft_agents.hosting.core import TurnContext

        reference = bot.reference_for(self.incoming())
        continuation = TurnContext.apply_conversation_reference(
            Activity(type=ActivityTypes.event, name="continue"),
            reference,
            is_incoming=False,
        )

        assert continuation.conversation.id == "19:abc@thread.tacv2"
        assert continuation.service_url == "https://smba.trafficmanager.net/br/"

    def test_round_tripping_the_continuation_would_break_it(self) -> None:
        """Pins the actual failure, so nobody reintroduces the dump/validate pair."""

        import pydantic
        from microsoft_agents.activity import Activity, ActivityTypes
        from microsoft_agents.hosting.core import TurnContext

        continuation = TurnContext.apply_conversation_reference(
            Activity(type=ActivityTypes.event, name="continue"),
            bot.reference_for(self.incoming()),
            is_incoming=False,
        )
        with pytest.raises(pydantic.ValidationError):
            Activity.model_validate(continuation.model_dump())


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
        self, text: str, attachments: Optional[list[Attachment]] = None
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
        claims = ClaimsIdentity(claims={}, is_authenticated=True)
        reply = InvokeResponse(status=200, body={"statusCode": 200})
        adapter = MagicMock()
        adapter.process_activity = AsyncMock(return_value=reply)
        monkeypatch.setattr(bot.bot, "claims_for", AsyncMock(return_value=claims))
        monkeypatch.setattr(bot.bot, "_adapter", adapter)
        on_turn = AsyncMock()

        result = await bot.handle(
            "Bearer ok",
            {"type": "invoke", "name": "adaptiveCard/action", "value": {}},
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
