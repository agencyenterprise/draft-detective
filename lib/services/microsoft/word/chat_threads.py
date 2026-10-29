"""The add-in chat's threads: one current conversation per account and document.

Scoped like handoffs, to the Microsoft account the pane is signed in as (its Entra
object id, and its tenant when known), never to an email address. A thread is found by
the document's URL the way handoffs are: Word reports different URL forms in different
clients, so a thread stores every key its URL yields and matches on any of them.

Clearing a chat stamps the thread rather than deleting it. The next message then starts
a new thread, and the old conversation stays in the checkpointer, out of the pane's reach.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.conversation import ConversationKind
from lib.models.microsoft_word_chat_thread import MicrosoftWordChatThread
from lib.services import conversations
from lib.services.microsoft.word.handoffs import Account, keys_for_url

# A document never saved has no URL. The pane sends a key of its own instead,
# ``unsaved:<id>`` (``chatDocumentKey`` in ``frontend/lib/addin/pane-document.ts``), so
# each unsaved document gets its own conversation. ``UNSAVED`` is only for a pane that
# sends nothing at all.
UNSAVED = "unsaved"
PANE_KEY_PREFIX = "unsaved:"


def thread_keys(url: str) -> list[str]:
    """The keys a thread for the document at ``url`` is stored and found under."""

    if keys := keys_for_url(url):
        return sorted(keys)
    url = url.strip()
    return [f"url:{url.lower()}"] if url else [UNSAVED]


def document_name(url: str) -> str:
    """A name for the document, from its URL. Word gives the pane nothing better.

    A ``…/_layouts/15/Doc.aspx?sourcedoc=…&file=Draft.docx`` link names the page in its
    path and the document in ``file``, so that wins when present.
    """

    if url.startswith(PANE_KEY_PREFIX):
        return "this document"
    parsed = urlparse(url)
    if named := parse_qs(parsed.query).get("file"):
        return named[0]
    name = PurePosixPath(unquote(parsed.path)).name
    return name or "this document"


def _owned_by(account: Account) -> Any:
    mine = col(MicrosoftWordChatThread.owner_oid) == account.oid
    if not account.tid:
        return mine
    return and_(
        mine,
        or_(
            col(MicrosoftWordChatThread.owner_tid).is_(None),
            col(MicrosoftWordChatThread.owner_tid) == account.tid,
        ),
    )


async def _current(
    session: AsyncSession, account: Account, url: str
) -> MicrosoftWordChatThread | None:
    wanted = set(thread_keys(url))
    rows = await session.execute(
        select(MicrosoftWordChatThread)
        .where(_owned_by(account))
        .where(col(MicrosoftWordChatThread.cleared_at).is_(None))
        .order_by(col(MicrosoftWordChatThread.last_turn_at).desc())
    )
    threads = list(rows.scalars().all())
    return next((t for t in threads if wanted & set(t.document_keys)), None)


async def current(account: Account, url: str) -> MicrosoftWordChatThread | None:
    """The account's uncleared thread for this document, the newest if several."""

    async with get_async_db_session() as session:
        return await _current(session, account, url)


async def current_or_new(
    account: Account, url: str, starter: conversations.Starter | None = None
) -> MicrosoftWordChatThread:
    """The current thread for this document, starting one if there is none.

    ``starter`` names the user a new thread is listed under, asked only when one starts.
    """

    if (thread := await current(account, url)) is not None:
        return thread
    user_id = await starter() if starter else None
    now = datetime.now(UTC)
    async with get_async_db_session() as session:
        # Two first messages at once (two panes, a retry) would otherwise each start a
        # thread: the lock makes the second wait, then find the first one's. Per account,
        # since one document has several URL forms; held until the commit.
        await session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtext(f"word-chat:{account.oid}"))
            )
        )
        if (thread := await _current(session, account, url)) is not None:
            return thread
        thread = MicrosoftWordChatThread(
            id=await conversations.start(session, ConversationKind.WORD, user_id),
            owner_oid=account.oid,
            owner_tid=account.tid,
            document_name=document_name(url),
            document_url=url,
            document_keys=thread_keys(url),
            created_at=now,
            last_turn_at=now,
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
    return thread


# A claim older than this is a turn that died without releasing it (a worker restart).
# Longer than any real turn: a long check runs for minutes.
STALE_CLAIM = timedelta(minutes=30)


async def claim(thread_id: uuid.UUID) -> datetime | None:
    """Take the thread for one turn: the claim's token, or None while another holds it.

    Two panes on one document, or a message and a resume, would otherwise run the agent
    on the same LangGraph thread at once, one checkpoint overwriting the other. The
    token is what ``release`` checks, so a turn can only let go of its own claim.
    """

    now = datetime.now(UTC)
    async with get_async_db_session() as session:
        claimed = await session.execute(
            update(MicrosoftWordChatThread)
            .where(col(MicrosoftWordChatThread.id) == thread_id)
            .where(
                or_(
                    col(MicrosoftWordChatThread.running_since).is_(None),
                    col(MicrosoftWordChatThread.running_since) < now - STALE_CLAIM,
                )
            )
            .values(running_since=now)
            .returning(col(MicrosoftWordChatThread.running_since))
        )
        token = claimed.scalar_one_or_none()
        await session.commit()
    return token


async def release(thread_id: uuid.UUID, token: datetime) -> None:
    """Let the next turn run, if this turn still holds the claim.

    A turn that stalled past ``STALE_CLAIM`` may have had its claim taken by another:
    releasing that one would let a third run alongside it.
    """

    async with get_async_db_session() as session:
        await session.execute(
            update(MicrosoftWordChatThread)
            .where(col(MicrosoftWordChatThread.id) == thread_id)
            .where(col(MicrosoftWordChatThread.running_since) == token)
            .values(running_since=None)
        )
        await session.commit()


async def begin_turn(thread_id: uuid.UUID) -> datetime | None:
    """Stamp a new turn, and return when the previous one began.

    The stamp puts the thread first among the account's threads for the document
    (``current``). What counts as news to the agent is not decided by time: each settled
    suggestion is told once, by ``heard_at`` (``chat_suggestions.unheard``).
    """

    async with get_async_db_session() as session:
        thread = await session.get(MicrosoftWordChatThread, thread_id)
        if thread is None:
            return None
        previous = thread.last_turn_at
        thread.last_turn_at = datetime.now(UTC)
        session.add(thread)
        await session.commit()
    return previous


async def clear(account: Account, url: str) -> bool:
    """Set the current thread aside, so the next message starts afresh.

    False when there was nothing to clear.
    """

    thread = await current(account, url)
    if thread is None:
        return False
    async with get_async_db_session() as session:
        await session.execute(
            update(MicrosoftWordChatThread)
            .where(col(MicrosoftWordChatThread.id) == thread.id)
            .where(_owned_by(account))
            .values(cleared_at=datetime.now(UTC))
        )
        await session.commit()
    return True
