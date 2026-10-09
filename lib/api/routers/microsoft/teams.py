"""The Teams bot's messaging endpoint.

One way in: ``/messages``, called by the Bot Connector. It authenticates with the token
the Connector presents and hands the activity to ``conversation.on_turn``; what the bot
does with it lives in ``lib/services/microsoft/teams/``. This module only maps the
outcome to what the Connector expects: an empty 200, an invoke's reply, or an error
status chosen so that the Connector retries only what a retry can fix.

Read-only, deliberately. A whole-file write back is refused with 423 while anyone has
the document open, whatever identity asks, so this path answers in chat and never
touches the document. Requests that really need a comment or a tracked change are
handed to the add-in, the only client that can write into a live session -- see
``lib/services/microsoft/word/handoffs.py``.

Two other transports were tried and removed. An outgoing webhook needed a Workflows
flow to post answers and could only reply in a separate message. A transport-neutral
``/ask`` endpoint outlived its purpose once the bot was the only caller.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from microsoft_agents.activity.invoke_response import InvokeResponse

from lib.services.microsoft.teams import bot, conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["microsoft", "teams"])


def _invoke_response(invoked: InvokeResponse) -> Response:
    """An invoke's reply, with the status and body the turn produced.

    The body is what Teams acts on -- for the sign-in card, the ``loginRequest`` that
    opens the sign-in window, or the card that replaces it -- so it is passed through
    rather than flattened into a blanket 200. The bodies are dicts this bot built.
    """

    if invoked.body is None:
        return Response(status_code=invoked.status)
    return JSONResponse(invoked.body, status_code=invoked.status)


@router.post("/messages")
async def bot_messages(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Response:
    """The bot's messaging endpoint, called by the Bot Connector.

    The turn acknowledges and ends; the answer follows about a minute later into
    the same thread. Keeping the request short is what lets Teams show a reply
    immediately instead of waiting on the model.

    Outside ``get_current_user``: the Bot Connector presents its own token, which
    the Agents SDK validates. That token is the authentication.
    """

    body = await request.json()

    try:
        invoked = await bot.handle(authorization, body, conversation.on_turn)
    except bot.NotConfigured as error:
        logger.error("the Teams bot is not configured: %s", error)
        raise HTTPException(
            status_code=503, detail="The bot is not configured"
        ) from error
    except PermissionError as error:
        logger.warning("a bot request failed token validation: %s", error)
        raise HTTPException(status_code=401, detail="Unauthorized") from error
    except bot.InvalidActivity as error:
        # 400 rather than 500 on purpose: the Connector retries a 5xx, and a payload
        # this SDK will not parse will not parse on the retry either. Logged at error
        # because the cost of the correct answer is that the message is dropped -- most
        # likely from schema drift between the Bot service and our pinned SDK, which
        # would otherwise be invisible.
        logger.error("could not parse a bot activity: %s", error)
        raise HTTPException(status_code=400, detail="Malformed activity") from error
    except Exception as error:  # noqa: BLE001 - the Connector retries on a 5xx
        logger.exception("could not process a bot activity")
        raise HTTPException(status_code=500, detail="Could not process") from error

    if invoked is not None:
        # An invoke -- the sign-in card's action -- is answered with the reply the turn
        # built. Teams reads that reply to decide whether to open the sign-in window or
        # replace the card; an empty 200 would do neither.
        return _invoke_response(invoked)

    # For everything else the Connector wants an empty 200; a body it would treat as
    # a payload.
    return Response(status_code=200)
