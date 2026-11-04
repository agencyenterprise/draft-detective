"""The Word add-in's chat with Draft Detective.

One continuing conversation per signed-in Microsoft account and document
(``lib/services/microsoft/word/chat_threads.py``), streamed the way the /chat page's
is: server-sent events of the same shape, from ``lib/services/chat``. The pane sends
the document's .docx along with a message whenever it changed, because only the pane
can read the document mid-edit (``lib/services/microsoft/word/pane_document.py``).

The agent's comments and tracked changes are suggestions until the person applies
them: stored as handoffs, read back here for the card, and applied, claimed and
reported through the same ``/word/handoffs`` routes as the ones from Teams.

Scoped like every add-in route, to the Microsoft account the pane signs in as
(``lib/api/addin_auth.py``), never to a Draft Detective user.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.types import Receive, Scope, Send

from lib.agents.deep_agent_setup import DEFAULT_MODEL, has_deployment_key
from lib.agents.tools.word_suggestions import DOCUMENT_PATH, SuggestionTarget
from lib.agents.word_chat_agent import (
    WordChatTurn,
    pending_suggestion,
    run_word_chat_resume,
    run_word_chat_turn,
    word_chat_reader,
)
from lib.agents.word_chat_checks import PaneCheck, pane_checks
from lib.api.addin_auth import AddinIdentity, get_addin_identity
from lib.config.env import config
from lib.models.microsoft_word_chat_thread import MicrosoftWordChatThread
from lib.services import users
from lib.services.chat.events import ChatEvent
from lib.services.chat.history import to_ui_messages
from lib.services.chat.sse import sse_stream
from lib.services.chat.thread_state import load_thread_messages, read_thread_file
from lib.services.files import images as file_images
from lib.services.microsoft import linked_users
from lib.services.microsoft.graph.documents import LoadedDocument
from lib.services.microsoft.word import chat_suggestions, chat_threads, pane_document
from lib.services.microsoft.word.chat_suggestions import ChatSuggestion
from lib.services.microsoft.word.handoffs import Account, Requester
from lib.services.microsoft.word.pane_document import NotADocument

logger = logging.getLogger(__name__)

# Mounted under the /word router (``word.py``), which every add-in route shares.
router = APIRouter(prefix="/chat", tags=["microsoft", "word"])

# Sent with a 409 when the conversation needs the document; the pane matches on it.
DOCUMENT_NEEDED = (
    "This conversation does not have the document yet: send it with the message."
)

# A document never saved has no URL: the pane sends a key of its own instead
# (``chatDocumentKey`` in ``frontend/lib/addin/pane-document.ts``).
URL_DESCRIPTION = (
    "The document URL Word reports, or `unsaved:<id>` for a document never saved"
)

# A whole .docx, images included.
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def _account(caller: AddinIdentity) -> Account:
    return Account(oid=caller.oid, tid=caller.tid)


class WordChatHistory(BaseModel):
    thread_id: UUID | None = Field(
        default=None, description="None until the first message to this document"
    )
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="In the shape the /chat page renders"
    )
    pending_suggestion_id: UUID | None = Field(
        default=None,
        description=(
            "The card the conversation is paused on, waiting for it to be applied or "
            "dismissed; the turn carries on through POST /thread/resume"
        ),
    )


class WordChatClearRequest(BaseModel):
    url: str = Field(description=URL_DESCRIPTION)


@router.get("/thread", response_model=WordChatHistory)
async def get_thread(
    url: str = Query(description=URL_DESCRIPTION),
    caller: AddinIdentity = Depends(get_addin_identity),
) -> WordChatHistory:
    """The current conversation about this document, if there is one."""

    thread = await chat_threads.current(_account(caller), url)
    if thread is None:
        return WordChatHistory()
    messages = to_ui_messages(
        await load_thread_messages(str(thread.id), reader=word_chat_reader)
    )
    return WordChatHistory(
        thread_id=thread.id,
        messages=messages,
        pending_suggestion_id=await pending_suggestion(thread.id),
    )


@router.post(
    "/thread/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_turn(
    url: Annotated[str, Form(description=URL_DESCRIPTION)],
    message: Annotated[str, Form(min_length=1, description="What they typed")],
    message_id: Annotated[
        str | None,
        Form(description="The id the pane already shows the message under"),
    ] = None,
    selection: Annotated[
        str | None, Form(description="The text selected in Word, if any")
    ] = None,
    document: Annotated[
        UploadFile | None,
        File(
            description=(
                "The .docx, when it changed since it was last sent in this thread. "
                "Left out, the agent keeps the copy it has."
            )
        ),
    ] = None,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> StreamingResponse:
    """Answer a message about the open document, streamed as server-sent events.

    Starts the conversation if there is none. Events are those of
    ``POST /api/chat/threads/{id}/stream``.

    Refused with 409 when the message comes without the document and the conversation
    has none: the pane only knows what it sent, not which conversation the message
    lands in (a document just saved gets a new one, and so does another account or a
    chat cleared in another pane). It sends again with the document.
    """

    loaded = await _read_document(url, document)
    account = _account(caller)
    if loaded is None:
        # Refused before anything is created: no thread, conversation or user for a
        # request that cannot run.
        existing = await chat_threads.current(account, url)
        if existing is None or not await _has_document(existing.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=DOCUMENT_NEEDED,
            )
    user_id = await _linked_user(caller)
    # Before the thread: a message that cannot be answered starts nothing.
    api_key = await _api_key(user_id)
    thread = await chat_threads.current_or_new(account, url, lambda: _given(user_id))
    token = await _claim(thread.id)
    try:
        if loaded is not None:
            await _swap_images(thread.id, loaded)
        await chat_threads.begin_turn(thread.id)
        suggestions = await chat_suggestions.for_thread(thread.id)
        unheard = [s.id for s in chat_suggestions.unheard(suggestions)]
        turn = WordChatTurn(
            thread_id=thread.id,
            text=message,
            message_id=message_id,
            document=loaded,
            selection=selection,
            suggestion_news=chat_suggestions.news(suggestions),
        )
        events = _released(
            run_word_chat_turn(turn, _target(caller, thread), api_key),
            thread.id,
            token,
            # Once the turn's first event arrives its input, news included, is stored.
            on_start=lambda: chat_suggestions.mark_heard(unheard),
        )
    except BaseException:
        await chat_threads.release(thread.id, token)
        raise
    return _ClaimedStream(events, thread.id, token)


# Sent with a 403 when there is no OpenAI key to answer with.
NO_API_KEY = (
    "Draft Detective needs your OpenAI API key to answer. Sign in to {frontend}/account "
    "with this Microsoft account's email address and add it there, then ask again."
)


async def _linked_user(caller: AddinIdentity) -> UUID | None:
    """The Draft Detective user this account is, by its email (``linked_users``).

    Found on every request rather than read off the conversation, which is linked only
    when it starts: a conversation started unlinked would otherwise never find the key
    its person adds later.
    """

    return await linked_users.user_for(caller.email_claim, caller.name, caller.tid)


async def _given(user_id: UUID | None) -> UUID | None:
    return user_id


async def _api_key(user_id: UUID | None) -> str | None:
    """The key to answer with: the person's own, as on /chat, else the deployment's.

    Theirs is the key saved by the user the account is linked to by email: the same
    trust the web app's Microsoft sign-in gives that email. Refused when neither has a
    key, rather than failing mid-answer.
    """

    own = await users.stored_api_key(user_id)
    if own is None and not has_deployment_key(DEFAULT_MODEL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=NO_API_KEY.format(frontend=config.FRONTEND_URL.rstrip("/")),
        )
    return own


# Sent with a 423 while another turn runs in the conversation (``chat_threads.claim``).
STILL_ANSWERING = "Draft Detective is still answering in this conversation."


async def _claim(thread_id: UUID) -> datetime:
    token = await chat_threads.claim(thread_id)
    if token is None:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=STILL_ANSWERING)
    return token


async def _released(
    events: AsyncIterator[ChatEvent],
    thread_id: UUID,
    token: datetime,
    on_start: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[ChatEvent]:
    """The turn's events, letting the conversation go however the stream ends.

    ``on_start`` runs once the first event arrives: by then the turn's input is stored.
    """

    try:
        started = False
        async for event in events:
            if not started and on_start is not None:
                started = True
                await on_start()
            yield event
    finally:
        await chat_threads.release(thread_id, token)


async def _swap_images(thread_id: UUID, loaded: LoadedDocument) -> None:
    """Keep the images of the document stored now and of the one coming in, no others.

    The stored document's stay: if this turn fails before the new one is stored, the
    conversation still reads the old one, and its images must still exist. The new ones
    are added first, so a file they share with a pruned row is still in use.
    """

    stored = await read_thread_file(
        str(thread_id), DOCUMENT_PATH, reader=word_chat_reader
    )
    await file_images.add_conversation_images(thread_id, loaded.images)
    keep = file_images.referenced_images(stored or "") | {i.id for i in loaded.images}
    await file_images.prune_conversation_images(thread_id, keep=keep)


class _ClaimedStream(StreamingResponse):
    """A turn's events as server-sent events, letting the conversation go once sent.

    ``_released`` lets it go when the events end, but a client gone before the body
    starts never runs them: without this the claim would hold until ``STALE_CLAIM``.
    """

    def __init__(
        self, events: AsyncIterator[ChatEvent], thread_id: UUID, token: datetime
    ) -> None:
        super().__init__(
            sse_stream(events),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        self._claim = (thread_id, token)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            # A second release of the same claim changes nothing.
            await chat_threads.release(*self._claim)


async def _has_document(thread_id: UUID) -> bool:
    return (
        await read_thread_file(str(thread_id), DOCUMENT_PATH, reader=word_chat_reader)
        is not None
    )


async def _read_document(
    url: str, document: UploadFile | None
) -> LoadedDocument | None:
    if document is None:
        return None
    # The upload is already received by now (Starlette spools a file part to disk,
    # with no size cap of its own), so this bounds what is read and converted, not
    # what was sent. A cap on what can be sent belongs to the proxy in front.
    payload = await document.read(MAX_DOCUMENT_BYTES + 1)
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"The document exceeds {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB",
        )
    try:
        return await pane_document.from_docx(
            payload,
            name=chat_threads.document_name(url),
            url=url,
        )
    except NotADocument as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"The document could not be read: {error}",
        ) from error


def _target(caller: AddinIdentity, thread: MicrosoftWordChatThread) -> SuggestionTarget:
    return SuggestionTarget(
        requester=Requester(oid=caller.oid, tid=caller.tid, upn=caller.email or ""),
        chat_thread_id=thread.id,
        document_name=thread.document_name,
        document_url=thread.document_url,
        document_keys=thread.document_keys,
    )


class WordChatResumeRequest(BaseModel):
    url: str = Field(description=URL_DESCRIPTION)


@router.post(
    "/thread/resume",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def resume_turn(
    request: WordChatResumeRequest,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> StreamingResponse:
    """Carry on the answer that paused on its card, once the card is applied or dismissed.

    Streamed as ``POST /thread/stream`` is. The agent reads the outcome from the card
    itself; nothing the pane sends is taken as the outcome. 409 when nothing is paused,
    or when the card is still waiting.
    """

    thread = await chat_threads.current(_account(caller), request.url)
    waiting_on = await pending_suggestion(thread.id) if thread else None
    if thread is None or waiting_on is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This conversation is not waiting on a card.",
        )
    card = await chat_suggestions.suggestion_for(waiting_on, _account(caller))
    if card is not None and card.status in ("pending", "applying"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The card has not been applied or dismissed yet.",
        )
    api_key = await _api_key(await _linked_user(caller))
    token = await _claim(thread.id)
    events = _released(
        run_word_chat_resume(thread.id, _target(caller, thread), api_key),
        thread.id,
        token,
    )
    return _ClaimedStream(events, thread.id, token)


@router.post("/thread/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_thread(
    request: WordChatClearRequest,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> Response:
    """Set this document's conversation aside; the next message starts a new one."""

    await chat_threads.clear(_account(caller), request.url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/suggestions/{suggestion_id}", response_model=ChatSuggestion)
async def get_suggestion(
    suggestion_id: UUID,
    caller: AddinIdentity = Depends(get_addin_identity),
) -> ChatSuggestion:
    """One set of the chat's suggestions, for its card: open, applied or dismissed."""

    suggestion = await chat_suggestions.suggestion_for(suggestion_id, _account(caller))
    if suggestion is None:
        raise HTTPException(status_code=404, detail="No suggestions with that id")
    return suggestion


@router.get("/checks", response_model=list[PaneCheck])
async def list_checks(
    _caller: AddinIdentity = Depends(get_addin_identity),
) -> list[PaneCheck]:
    """The checks the chat offers to run from its list, without the internet."""

    return pane_checks()
