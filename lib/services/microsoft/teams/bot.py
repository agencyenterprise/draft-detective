"""Draft Detective as a Teams bot.

The webhook prototype worked but cost too many manual steps and could only answer
in a separate message. A bot gets the proper thing: its own identity and icon,
replies threaded under the question, typing indicators, and it works in channels,
group chats and one-to-one alike.

Built on the Microsoft 365 Agents SDK. ``botbuilder-python`` is end of life -- the
repository was archived in January 2026 -- and this is its supported successor.
Only ``hosting-core`` is used, not ``hosting-aiohttp``: the core does not depend on
a web framework, so the FastAPI route in
``lib/api/routers/microsoft/teams.py`` stays ours while the SDK handles the part
worth not hand-rolling, which is validating the token Teams presents. Its
``AgentApplication`` layer is not used either: the bot handles two kinds of activity,
and ``conversation.py`` dispatches them itself.

Answering takes about a minute, far longer than the request should stay open. So a
turn acknowledges and ends, and the answer is delivered afterwards through
``process_proactive`` against the conversation reference, which is what puts it in
the same thread rather than in a new message.

**A question is only ever answered with a token for the person who asked**, so the
bot can reach nothing they could not. Getting that token is ``sign_in.py``'s job, through
the OAuth connection named by ``TEAMS_USER_AUTH_CONNECTION``, and it works in channels
too. The bot will not start without that connection.

One thing the user token does *not* solve: the answer is posted into the conversation
the question came from, so in a channel it is visible to everyone in that channel,
access to the document or not. Gating the read closes "I cannot open it, so I will ask
the bot"; it does not close "someone who can open it asks somewhere I can see".
"""

import html
import json
import logging
import re
from collections.abc import Awaitable, Iterator
from typing import Any, Callable, Optional

from microsoft_agents.activity import Activity, ActivityTypes, ConversationReference
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.activity.invoke_response import InvokeResponse
from microsoft_agents.hosting.core import (
    AgentAuthConfiguration,
    AuthenticationConstants,
    AuthTypes,
    ChannelServiceAdapter,
    ClaimsIdentity,
    JwtTokenValidator,
    RestChannelServiceClientFactory,
    TurnContext,
)
from pydantic import ValidationError

from lib.config.env import config

logger = logging.getLogger(__name__)

# The SDK looks this key up by name and refuses to build without it.
CONNECTION = "SERVICE_CONNECTION"
BOT_AUDIENCE = "https://api.botframework.com"

# What runs for each activity once it has been authenticated.
TurnHandler = Callable[[TurnContext], Awaitable[None]]

# Backslash is excluded along with the quotes: a URL never contains one, and these
# are read out of JSON and HTML where it is the escape character.
_SHAREPOINT_URL = re.compile(r"https://[\w.-]+\.sharepoint\.com/[^\s<>\"'\\]+", re.I)

# Teams' preview endpoints sit on the same host as the document itself, so a card's
# thumbnail would otherwise be taken for the thing it is a picture of.
_NOT_A_DOCUMENT = ("getpreview.ashx", "thumbnail.ashx", "/_api/", "/_vti_")


class NotConfigured(Exception):
    """Raised when the bot's credentials are absent, so it cannot be trusted."""


class InvalidActivity(Exception):
    """Raised when the body is not an activity this SDK will parse.

    Its own type so the route can answer 400 rather than 500, and that distinction is
    the same one that already matters for a bad token: the Bot Connector retries a 5xx
    and gives up on a 4xx. A payload we cannot parse will not parse on the retry
    either, so a 500 here turns one malformed -- or merely newer -- activity into
    sustained load. ``Activity`` is strict enough for that to be a live risk: it once
    rejected all thirty fields of an activity this codebase built itself.
    """


def _auth_configuration() -> AgentAuthConfiguration:
    if not config.TEAMS_BOT_APP_ID or not config.TEAMS_BOT_APP_PASSWORD:
        raise NotConfigured(
            "TEAMS_BOT_APP_ID and TEAMS_BOT_APP_PASSWORD must be set before the bot "
            "can accept a request"
        )
    if not config.TEAMS_USER_AUTH_CONNECTION:
        raise NotConfigured(
            "TEAMS_USER_AUTH_CONNECTION must name the OAuth connection on the Azure Bot "
            "resource: the bot reads documents only as the person who asked"
        )
    return AgentAuthConfiguration(
        auth_type=AuthTypes.client_secret,
        client_id=config.TEAMS_BOT_APP_ID,
        client_secret=config.TEAMS_BOT_APP_PASSWORD,
        # Only for a single-tenant bot; a multi-tenant one must not pin an authority.
        tenant_id=config.TEAMS_BOT_TENANT_ID or None,
    )


class _Bot:
    """The adapter and token validator, built once and reused.

    Held lazily rather than at import: the credentials may be absent in a
    deployment that does not run the bot, and that should not stop the service
    starting.
    """

    def __init__(self) -> None:
        self._adapter: Optional[ChannelServiceAdapter] = None
        self._validator: Optional[JwtTokenValidator] = None

    def _build(self) -> None:
        if self._adapter is not None:
            return
        auth = _auth_configuration()
        connections = MsalConnectionManager(
            connections_configurations={CONNECTION: auth}
        )
        self._adapter = ChannelServiceAdapter(
            RestChannelServiceClientFactory(connections)
        )
        self._validator = JwtTokenValidator(auth)
        logger.info(
            "Teams bot ready for app id %s, signing users in with %r",
            config.TEAMS_BOT_APP_ID,
            config.TEAMS_USER_AUTH_CONNECTION,
        )

    @property
    def adapter(self) -> ChannelServiceAdapter:
        self._build()
        assert self._adapter is not None
        return self._adapter

    async def claims_for(self, authorization: Optional[str]) -> ClaimsIdentity:
        """Who sent this, according to the token Teams presented.

        Raises if the token is missing or does not verify. This is the only thing
        standing between the endpoint and anyone who can reach it, which is why it
        is the SDK's job and not ours.
        """

        if not authorization or not authorization.lower().startswith("bearer "):
            raise PermissionError("no bearer token")
        self._build()
        assert self._validator is not None
        try:
            return await self._validator.validate_token(
                authorization.split(" ", 1)[1].strip()
            )
        except PermissionError:
            raise
        except Exception as error:
            # A token the SDK will not accept is a refusal, not a server fault. The
            # difference matters: the Bot Connector retries a 5xx and gives up on a
            # 401, so mislabelling this produces a retry storm.
            raise PermissionError(f"token rejected: {error}") from error


bot = _Bot()


def question_from(context: TurnContext) -> str:
    """The question, as asked, without the mention of the bot.

    The SDK removes the mention from the activity's text using the entity metadata
    Teams sends rather than guessing from the markup. What is left to do is normalise
    the whitespace that leaves behind.
    """

    text = context.activity.remove_recipient_mention() or ""
    return " ".join(text.split()).strip()


def _scannable(activity: Activity) -> Iterator[str]:
    """Every part of a message that could carry a link, most faithful first.

    ``activity.text`` is only the *visible* text. Teams renders a pasted link as a
    hyperlink whose anchor is the file name, and the href does not appear there at
    all -- so a message that plainly contains a link arrives looking like a bare file
    name. The href survives in the attachments Teams sends alongside: the message's
    own HTML, and the card it unfurls a SharePoint link into.
    """

    yield activity.text or ""
    for attachment in activity.attachments or []:
        content = attachment.content
        if isinstance(content, str):
            yield content
        elif content is not None:
            # Shape-agnostic on purpose. Teams has several card types for a file and
            # the href sits under a different key in each, so the whole card is
            # scanned rather than one guessed-at field.
            yield json.dumps(content, default=str)
        if attachment.content_url:
            yield attachment.content_url


def document_urls_in(activity: Activity) -> list[str]:
    """Every SharePoint link in this message, in the order they were found.

    All of them rather than the first, because which one is meant is a question about
    the conversation -- "compare these two", "the second one" -- and that is the agent's
    to answer, not a regex's. They are candidates handed over, not a decision made here.

    Trailing punctuation is trimmed: Teams decorates a pasted link, and an href in
    HTML arrives escaped, so a match is cleaned rather than used raw. Duplicates are
    dropped because the same link appears in the text, the HTML and the card.
    """

    found: list[str] = []
    for text in _scannable(activity):
        for match in _SHAREPOINT_URL.finditer(html.unescape(text)):
            url = match.group(0).rstrip(").,;'\"")
            if any(marker in url.lower() for marker in _NOT_A_DOCUMENT):
                continue
            if url not in found:
                found.append(url)
    return found


def reference_for(activity: Activity) -> ConversationReference:
    """Where to send the answer so it lands under the question."""

    return activity.get_conversation_reference()


async def send_typing(context: TurnContext) -> None:
    """Show that something is happening, since the answer is a minute away."""

    try:
        await context.send_activity(Activity(type=ActivityTypes.typing))
    except Exception as error:  # noqa: BLE001 - cosmetic, never worth failing for
        logger.debug("could not send a typing indicator: %s", error)


async def post_later(reference: ConversationReference, text: str) -> None:
    """Send a message into a conversation after its turn has ended.

    Never raises: by this point the request has been answered and there is nobody
    to return an error to, so a failure is logged instead.
    """

    async def deliver(context: TurnContext) -> None:
        await context.send_activity(Activity(type=ActivityTypes.message, text=text))

    # Used as returned, not round-tripped through model_dump/model_validate:
    # model_dump emits None for every unset optional field, and validating that
    # back fails on all thirty of them.
    continuation = TurnContext.apply_conversation_reference(
        Activity(type=ActivityTypes.event, name="continue"),
        reference,
        is_incoming=False,
    )
    # The adapter needs to know who is sending, since there is no inbound request
    # to infer it from.
    identity = ClaimsIdentity(
        claims={
            AuthenticationConstants.AUDIENCE_CLAIM: config.TEAMS_BOT_APP_ID or "",
            AuthenticationConstants.APP_ID_CLAIM: config.TEAMS_BOT_APP_ID or "",
        },
        is_authenticated=True,
    )

    try:
        await bot.adapter.process_proactive(
            identity, continuation, BOT_AUDIENCE, deliver
        )
        logger.info("posted a follow-up to Teams (%s chars)", len(text))
    except Exception as error:  # noqa: BLE001
        logger.error("could not post the follow-up to Teams: %s", error)


async def handle(
    authorization: Optional[str], body: dict[str, Any], on_turn: TurnHandler
) -> Optional[InvokeResponse]:
    """Authenticate one activity and run ``on_turn`` for it.

    Returns the reply to an invoke -- what ``on_turn`` answered it with -- and None for
    anything else. An invoke ``on_turn`` did not answer comes back as a 501.
    """

    claims = await bot.claims_for(authorization)
    try:
        activity = Activity.model_validate(body)
    except ValidationError as error:
        # Distinguished from a server fault so the route can answer 400. Retrying an
        # unparseable payload cannot help, and the Connector retries a 5xx.
        raise InvalidActivity(str(error)) from error

    return await bot.adapter.process_activity(claims, activity, on_turn)
