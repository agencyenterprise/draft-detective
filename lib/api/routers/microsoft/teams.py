"""Answering questions about a document from outside Word.

A request arriving from a Teams channel has no Word session to borrow, so the
service loads the document itself. That works: Graph serves what SharePoint last
persisted, which is current when nobody is editing and trails a live edit by under
a second.

Read-only, deliberately. A whole-file write back is refused with 423 while anyone
has the document open, whatever identity asks, so this path answers in chat and
never touches the document. Requests that really need a comment or a tracked change
belong to the add-in, which is the only client that can write into a live session.

One way in: ``/messages``, the bot's endpoint. It authenticates with the token the
Bot Connector presents, acknowledges immediately, and posts the answer into the same
thread about a minute later.

Which document to read is not decided here. Every link in the message is passed along as
a candidate and the agent opens what it needs, because which one is meant depends on what
was asked. A link is the only way in: there is no lookup by name, because searching on
someone's behalf could reach documents they cannot open. A follow-up in the same thread
needs no link, since the agent remembers what it already opened there and re-checks it
as the person asking now. Only a document the thread has not seen gets a request for the
link.

Two other transports were tried and removed. An outgoing webhook needed a Workflows
flow to post answers and could only reply in a separate message. A transport-neutral
``/ask`` endpoint outlived its purpose once the bot was the only caller.
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from lib.agents.teams_agent import answer_question
from lib.services.microsoft.graph.client import redacted
from lib.services.microsoft.teams import bot, sign_in

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["microsoft", "teams"])

# A detached task is only weakly referenced by the event loop, so without this the
# answer can be garbage collected mid-flight.
_running: set[asyncio.Task[None]] = set()

APOLOGY = "I could not work that one out, sorry."

# The token service is down or erroring. Said rather than raised: a 5xx here would only
# be retried by the Connector, and the person would hear nothing either way.
SIGN_IN_UNAVAILABLE = (
    "I cannot reach the sign-in service right now, so I have not read anything. "
    "Please try again in a few minutes."
)


def _finished(task: "asyncio.Task[None]") -> None:
    """Retire a detached task, and make sure a failure in one cannot vanish.

    Discarding the reference without reading the result is what asyncio calls an
    unretrieved exception: it surfaces as a warning at interpreter shutdown, if at all,
    while the person who was told "I will follow up here shortly" waits forever.

    This is a backstop rather than the handler. ``_answer_into_thread`` catches its own
    failures, because that is where the conversation is still reachable and something
    can be said. Reaching here means the failure was outside even that -- a
    ``BaseException``, or a fault in the apology itself.
    """

    _running.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        # Shutdown cancelling in-flight work is not a fault.
        pass
    except Exception:  # noqa: BLE001 - a lost answer must not also be a silent one
        logger.exception("a detached answer task failed after the turn ended")


def _invoke_response(invoked: Any) -> Response:
    """An invoke's reply, with the status and body the turn produced.

    The body is what Teams acts on -- for the sign-in card, the ``loginRequest`` that
    opens the sign-in window, or the card that replaces it -- so it is passed through
    rather than flattened into a blanket 200. The bodies are dicts this bot built.
    """

    if invoked.body is None:
        return Response(status_code=invoked.status)
    return JSONResponse(invoked.body, status_code=invoked.status)


def _start_answering(
    reference: Any,
    question: str,
    author: str,
    conversation: str,
    document_urls: list[str],
    graph_token: str,
) -> None:
    """Answer in the background; the answer is posted into the thread when ready.

    Detached rather than a FastAPI background task: the answer is posted proactively,
    so it does not belong to this request's lifecycle, and the handler must not depend
    on anything the request owns.
    """

    task = asyncio.create_task(
        _answer_into_thread(
            reference, question, author, conversation, document_urls, graph_token
        )
    )
    _running.add(task)
    task.add_done_callback(_finished)


async def _answer_into_thread(
    reference: Any,
    question: str,
    author: str,
    conversation: str,
    document_urls: list[str],
    graph_token: str,
) -> None:
    """Ask, and post the answer back into the thread the question came from.

    No document is loaded here, and none is chosen. The links found in the message go
    along as candidates and the agent opens what it needs -- which also means a document
    that is missing, not allowed, or not readable *by the person asking* comes back as
    something the agent can explain, rather than as an exception this function has to
    translate.

    Detached from the request, so nothing here can return an error to a caller. A
    failure is posted into the conversation instead: leaving someone waiting for a
    reply that never arrives is worse than telling them it went wrong. The person has
    already been told an answer is coming, so *every* way out of this function ends in
    something being said -- which is why the raise is handled here, where the
    conversation is still in reach, rather than only in the task's done callback.
    """

    try:
        answer = await answer_question(
            question=question,
            graph_token=graph_token,
            # The Teams conversation *is* the agent's thread, which is what makes a
            # follow-up here a follow-up there. In a channel this id already carries a
            # ``;messageid=`` suffix per reply chain, so separate chains are separate
            # conversations without anything having to parse it.
            thread_id=conversation,
            document_urls=document_urls,
            asked_by=author,
            user_id=author,
        )
    except Exception:  # noqa: BLE001 - nobody upstream to hand this to
        # ``answer_question`` reports a failure rather than raising, so arriving here
        # means something outside its own guard broke. Truncated like the request log:
        # a question can quote the document, and what is reviewed here is confidential.
        logger.exception("could not answer %r", question[:120])
        await bot.post_later(reference, APOLOGY)
        return

    if answer.failed:
        logger.error("could not answer %r: %s", question[:120], answer.error)
        await bot.post_later(reference, APOLOGY)
        return

    await bot.post_later(reference, answer.text)


@bot.on_question
async def _on_question(context: Any, state: Any) -> None:
    """Acknowledge a question and hand the answering off.

    Registered on the bot's application at import rather than per request, so it must
    close over nothing belonging to one request. When the asker has not signed in yet,
    the question is parked and they are shown a sign-in card instead; it is answered
    from ``_on_sign_in_action`` once they have.
    """

    question = bot.question_from(context)
    author = (
        context.activity.from_property.name
        if context.activity.from_property
        else "someone"
    )
    conversation = (
        context.activity.conversation.id if context.activity.conversation else ""
    )

    if not question:
        await context.send_activity(
            "Mention me with a question about the document and I will take a look."
        )
        return

    # From the activity, not the question: Teams shows a pasted link as a
    # hyperlink and keeps the href out of the text entirely. All of them, because
    # choosing between them is the agent's job.
    document_urls = bot.document_urls_in(context.activity)
    logger.info(
        "Teams bot question from %s: %r (links: %s)",
        author,
        question[:120],
        ", ".join(redacted(url) for url in document_urls) or "none found",
    )
    if not document_urls and ".doc" in question.lower():
        # Someone named a document but no href was found anywhere in the activity.
        # Teams keeps a rendered hyperlink's href in an attachment rather than in
        # the text, and which attachment depends on how the link was shared, so
        # what is logged is the shapes that were present. Deliberately not the
        # payload: it carries the message body and the sender's ids, and the
        # documents discussed here are confidential.
        logger.warning(
            "a message named a document but carried no link; attachments were: %s",
            [
                attachment.content_type
                for attachment in context.activity.attachments or []
            ],
        )

    # The asker's own token: every document is read with their access. Fetched inside
    # the turn, while the context that carries the sender is still available, and
    # handed to the detached task rather than looked up there. None means they have
    # not signed in yet.
    try:
        graph_token = await sign_in.user_token(context)
    except sign_in.TokenServiceUnavailable as error:
        logger.error("could not check %s's sign-in: %s", author, error)
        await context.send_activity(SIGN_IN_UNAVAILABLE)
        return
    if graph_token is None:
        pending = sign_in.pending_from(
            context.activity, question, author, document_urls
        )
        pending_id = await sign_in.park(pending)
        await sign_in.ask_to_sign_in(context, pending_id, pending)
        logger.info("asked %s to sign in before answering (%s)", author, pending_id)
        return

    await bot.send_typing(context)
    await context.send_activity("Looking at that now — I will follow up here shortly.")
    _start_answering(
        bot.reference_for(context.activity),
        question,
        author,
        conversation,
        document_urls,
        graph_token,
    )


@bot.on_sign_in_action
async def _on_sign_in_action(context: Any, state: Any) -> None:
    """The sign-in card's action: sign the asker in, then answer what they asked.

    Arrives each time anyone presses the card's button, and once more after a sign-in.
    Without a token the reply is a login request, which is what makes Teams open the
    sign-in window. With one -- which after a sign-in means redeeming the ``state``
    Teams sends back -- the parked question is taken and answered.

    Only the asker can release their question. Anyone in the channel can press the
    button, and answering with the presser's token would read the document with the
    wrong person's access.
    """

    activity = context.activity
    pending_id = sign_in.pending_id_of(activity)
    pending = await sign_in.peek(pending_id) if pending_id else None
    presser = activity.from_property.id if activity.from_property else ""
    if pending is not None and pending.asker_id != presser:
        await sign_in.tell(
            context,
            f"This sign-in is for {pending.author}. Mention me with your own "
            "question and I will ask you to sign in.",
        )
        return

    try:
        graph_token = await sign_in.user_token(
            context, magic_code=sign_in.magic_code_of(activity)
        )
        if graph_token is None:
            await sign_in.request_sign_in(context)
            return
    except sign_in.TokenServiceUnavailable as error:
        logger.error("could not complete a sign-in: %s", error)
        await sign_in.tell(context, SIGN_IN_UNAVAILABLE)
        return

    # Taken rather than read: the button can be pressed twice, and the question must be
    # answered once.
    pending = await sign_in.take(pending_id) if pending_id else None
    await sign_in.show_signed_in(context, answering=pending is not None)
    if pending is None:
        return

    logger.info("%s signed in; answering their parked question", pending.author)
    _start_answering(
        pending.conversation_reference(),
        pending.question,
        pending.author,
        pending.conversation,
        pending.document_urls,
        graph_token,
    )


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
        invoked = await bot.handle(authorization, body)
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
