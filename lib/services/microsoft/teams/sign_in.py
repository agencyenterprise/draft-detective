"""Signing someone in from wherever they asked, channels included.

The Bot Framework's sign-in card -- the ``OAuthCard`` -- only works in a one-to-one chat.
Teams refuses it in a channel or a group chat with "this action can't be performed since
the app does not exist or has been uninstalled", so everyone had to find the bot's
personal chat and sign in there before a channel mention could work.

An Adaptive Card ``Action.Execute`` is the one route Teams documents for signing in
inside the conversation itself. The bot posts a card with a Sign in button; when its
action reaches the bot and there is no token, the bot answers the invoke with a
``loginRequest`` instead of a card, and Teams opens the sign-in window. Once the person
signs in, Teams sends the same action again carrying a ``state`` code, which the Bot
Framework token service redeems for their token. It is the OAuth connection named by
``TEAMS_USER_AUTH_CONNECTION``, and the token service holds the refresh token.

The question waits in ``pending_questions.py`` while this happens. It is keyed by an id
the card carries, not by who clicked, and only the person who asked can release it:
anyone in the channel can press the card's button, and the answer must be read with the
asker's access, not theirs.

Reference: https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/universal-actions-for-adaptive-cards/authentication-flow-in-universal-action-for-adaptive-cards
"""

import logging
from typing import Any, Optional

from aiohttp import ClientError, ClientResponseError
from microsoft_agents.activity import Activity, ActivityTypes, Attachment
from microsoft_agents.activity.invoke_response import InvokeResponse
from microsoft_agents.hosting.core import TurnContext
from microsoft_agents.hosting.core.connector import UserTokenClientBase

from lib.config.env import config

logger = logging.getLogger(__name__)

# The SDK logs every non-200 from the token service at ERROR before raising, and "this
# person has not signed in yet" is a 404 -- the normal path for every first question.
# The failures that matter are logged here instead, as TokenServiceUnavailable.
logging.getLogger("microsoft_agents.hosting.core.connector.client.user_token").setLevel(
    logging.CRITICAL
)

# Namespaced: Teams delivers every card action to the bot, and this is the only one
# that should start or finish a sign-in.
VERB = "draftDetective.signIn"

_CARD = "application/vnd.microsoft.card.adaptive"
_LOGIN_REQUEST = "application/vnd.microsoft.activity.loginRequest"
_INVALID_AUTH_CODE = "application/vnd.microsoft.error.invalidAuthCode"
_MESSAGE = "application/vnd.microsoft.activity.message"


class TokenServiceUnavailable(Exception):
    """Raised when the Bot Framework token service cannot be reached or fails.

    Distinct from "not signed in", which is an answer rather than a failure: this one
    means nobody can be signed in or read as right now, and the person should be told
    so rather than shown a sign-in card that cannot work.
    """


def _token_client(context: TurnContext) -> UserTokenClientBase:
    # Keyed by the abstract base, as the adapter registers it; mypy only expects
    # concrete classes as keys.
    client = context.services.get(UserTokenClientBase)  # type: ignore[type-abstract]
    if client is None:
        raise RuntimeError("the adapter did not provide a user token client")
    return client


async def user_token(
    context: TurnContext, magic_code: Optional[str] = None
) -> Optional[str]:
    """The sender's Graph token, or None when they have not signed in.

    Asks the Bot Framework token service, which holds the refresh token and refreshes
    on our behalf. ``magic_code`` is the ``state`` Teams returns after a sign-in, which
    the token service exchanges for the token.

    Raises ``TokenServiceUnavailable`` when the token service cannot answer.
    """

    activity = context.activity
    if not activity.from_property or not activity.from_property.id:
        return None
    try:
        response = await _token_client(context).get_user_token(
            user_id=activity.from_property.id,
            connection_name=config.TEAMS_USER_AUTH_CONNECTION or "",
            channel_id=activity.channel_id or "",
            magic_code=magic_code,
        )
    except ClientResponseError as error:
        # The token service answers "no token for this user" with a 404, and the SDK
        # raises on it rather than returning an empty response.
        if error.status == 404:
            return None
        raise TokenServiceUnavailable(
            f"token service answered {error.status}"
        ) from error
    except (ClientError, TimeoutError) as error:
        raise TokenServiceUnavailable(f"token service unreachable: {error}") from error
    return str(response.token) if response and response.token else None


async def _sign_in_link(context: TurnContext) -> str:
    try:
        resource = await _token_client(context).get_sign_in_resource(
            connection_name=config.TEAMS_USER_AUTH_CONNECTION or "",
            activity=context.activity,
        )
    except (ClientError, TimeoutError) as error:
        raise TokenServiceUnavailable(f"no sign-in link: {error}") from error
    return str(resource.sign_in_link)


def _card(pending_id: str, question: str) -> dict[str, Any]:
    action = {
        "type": "Action.Execute",
        "verb": VERB,
        "title": "Sign in",
        "data": {"pending": pending_id},
    }
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Sign in so I can read the document as you",
                "weight": "Bolder",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    "I only open documents you can open yourself. Once you are signed "
                    f"in I will answer: {question[:200]}"
                ),
                "isSubtle": True,
                "wrap": True,
            },
        ],
        "actions": [action],
    }


def _done_card(text: str) -> dict[str, Any]:
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [{"type": "TextBlock", "text": text, "wrap": True}],
    }


async def ask_to_sign_in(context: TurnContext, pending_id: str, question: str) -> None:
    """Post the card whose button signs the asker in and releases their question."""

    await context.send_activity(
        Activity(
            type=ActivityTypes.message,
            attachments=[
                Attachment(content_type=_CARD, content=_card(pending_id, question))
            ],
        )
    )


def is_sign_in_action(activity: Activity) -> bool:
    if activity.type != ActivityTypes.invoke or activity.name != "adaptiveCard/action":
        return False
    value = activity.value if isinstance(activity.value, dict) else {}
    action = value.get("action") or {}
    return isinstance(action, dict) and action.get("verb") == VERB


def pending_id_of(activity: Activity) -> Optional[str]:
    value = activity.value if isinstance(activity.value, dict) else {}
    data = (value.get("action") or {}).get("data") or {}
    pending_id = data.get("pending") if isinstance(data, dict) else None
    return str(pending_id) if pending_id else None


def magic_code_of(activity: Activity) -> Optional[str]:
    value = activity.value if isinstance(activity.value, dict) else {}
    state = value.get("state")
    return str(state) if state else None


async def _reply(context: TurnContext, body: dict[str, Any]) -> None:
    """Answer the card action's invoke.

    Always HTTP 200: an ``adaptiveCard/action`` reply carries its outcome in the body's
    ``statusCode``, and the 401 of a ``loginRequest`` lives there, not on the response.
    """

    await context.send_activity(
        Activity(
            type=ActivityTypes.invoke_response,
            value=InvokeResponse(status=200, body=body).model_dump(exclude_unset=True),
        )
    )


async def request_sign_in(context: TurnContext) -> None:
    """Have Teams open the sign-in window, in the conversation itself.

    Raises ``TokenServiceUnavailable`` when no sign-in link can be had.
    """

    await _reply(
        context,
        {
            "statusCode": 401,
            "type": _LOGIN_REQUEST,
            "value": {
                "text": "Sign in",
                "connectionName": config.TEAMS_USER_AUTH_CONNECTION or "",
                "buttons": [
                    {
                        "title": "Sign in",
                        "text": "Sign in",
                        "type": "signin",
                        "value": await _sign_in_link(context),
                    }
                ],
            },
        },
    )


async def reject_code(context: TurnContext) -> None:
    """Tell Teams the sign-in code it sent back did not redeem.

    The reply the Universal Actions protocol defines for a bad ``state``: Teams can
    prompt again or resend the action, rather than treating the sign-in as done.
    """

    await _reply(context, {"statusCode": 401, "type": _INVALID_AUTH_CODE})


async def show_signed_in(context: TurnContext, answering: bool) -> None:
    text = (
        "You are signed in. Looking at it now — I will follow up in this thread."
        if answering
        else "You are signed in. Mention me again if you still need an answer."
    )
    await _reply(context, {"statusCode": 200, "type": _CARD, "value": _done_card(text)})


async def tell(context: TurnContext, text: str) -> None:
    """A short notice for whoever pressed the button, and nobody else."""

    await _reply(context, {"statusCode": 200, "type": _MESSAGE, "value": text})
