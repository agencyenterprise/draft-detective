"""Questions waiting for their askers to sign in, shared across workers.

When someone without a token asks the bot something, the question is parked here and
they are shown a sign-in card (``sign_in.py``). It is taken back out by the card action
that follows the sign-in -- a *different request*, which in production usually lands on
a *different process*, since Uvicorn is launched with ``--workers 4``. Process memory
cannot span that, so first-time sign-in would fail about three times in four, and only
once deployed: a single-process dev server never shows it.

One short transaction per operation, no locks. Each question gets a fresh id, so a
park never collides with another.

**Rows are swept, because a sign-in nobody finishes never takes its question back.**
The rows that linger are the ones where somebody saw the Sign in card and walked away --
and what is stored is the question itself, meaning its text and its sender. Left alone,
that is confidential content retained indefinitely in a table whose rows otherwise live
for a minute or two. Every park therefore drops rows older than ``ABANDONED_AFTER``,
which costs an indexed range delete and needs no scheduler.

No tokens pass through here. The refresh token stays in the Bot Framework token
service; what is stored is the question waiting to be answered, and where to answer it.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from microsoft_agents.activity import Activity, ConversationReference
from pydantic import BaseModel
from sqlalchemy import CursorResult, delete, insert, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.microsoft_teams_signin_state import MicrosoftTeamsSignInState

logger = logging.getLogger(__name__)

# Generous next to the thing being measured: a sign-in takes about a minute, so a row
# untouched for an hour belongs to a sign-in that was abandoned rather than one still in
# progress. Long enough that a slow sign-in is never swept out from under someone, short
# enough that a parked message is not kept for days.
ABANDONED_AFTER = timedelta(hours=1)

# Rows are keyed by this prefix and the id the sign-in card carries. Kept from when the
# table also held the Agents SDK's own entries: a card posted before a deploy still
# carries a bare id, and its question was stored under the prefixed key.
_KEY_PREFIX = "pending-question/"


def _key(pending_id: str) -> str:
    return _KEY_PREFIX + pending_id


class PendingQuestion(BaseModel):
    """A question waiting for its asker to sign in.

    Everything needed to answer it later, from a different request and possibly a
    different worker. The conversation reference is what puts the answer back in the
    thread the question came from, and it already names the asker and the conversation.
    """

    question: str
    author: str
    document_urls: list[str]
    reference: dict[str, Any]

    def conversation_reference(self) -> ConversationReference:
        return ConversationReference.model_validate(self.reference)

    @property
    def asker_id(self) -> str:
        user = self.conversation_reference().user
        return user.id if user and user.id else ""

    @property
    def conversation(self) -> str:
        conversation = self.conversation_reference().conversation
        return conversation.id if conversation else ""


def pending_from(
    activity: Activity, question: str, author: str, document_urls: list[str]
) -> PendingQuestion:
    return PendingQuestion(
        question=question,
        author=author,
        document_urls=document_urls,
        reference=activity.get_conversation_reference().model_dump(
            mode="json", by_alias=True, exclude_none=True
        ),
    )


async def park(pending: PendingQuestion) -> str:
    """Store a question until its asker signs in, and return the id that finds it."""

    pending_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    async with get_async_db_session() as session:
        await session.execute(
            insert(MicrosoftTeamsSignInState).values(
                key=_key(pending_id),
                value=pending.model_dump(mode="json"),
                updated_at=now,
            )
        )
        # Same transaction as the park, so a sweep cannot be the thing that fails on its
        # own and leaves the caller thinking nothing happened. A DELETE really does come
        # back as a CursorResult, which carries rowcount; the stubs only promise the
        # narrower Result.
        swept = cast(
            CursorResult[Any],
            await session.execute(
                delete(MicrosoftTeamsSignInState).where(
                    col(MicrosoftTeamsSignInState.updated_at) < now - ABANDONED_AFTER
                )
            ),
        )
        await session.commit()

    if swept.rowcount:
        logger.info("swept %s abandoned Teams question(s)", swept.rowcount)
    return pending_id


async def peek(pending_id: str) -> Optional[PendingQuestion]:
    """The question, left in place."""

    async with get_async_db_session() as session:
        value = (
            await session.execute(
                select(col(MicrosoftTeamsSignInState.value)).where(
                    col(MicrosoftTeamsSignInState.key) == _key(pending_id)
                )
            )
        ).scalar_one_or_none()
    return PendingQuestion.model_validate(value) if value else None


async def take(pending_id: str) -> Optional[PendingQuestion]:
    """Remove the question and return it, in one statement.

    A read followed by a delete would let two requests both see it. Taking a parked
    question has to be exclusive -- the button can be pressed twice, and Teams retries an
    invoke it did not hear back from -- or the question is answered twice.
    """

    async with get_async_db_session() as session:
        value = (
            await session.execute(
                delete(MicrosoftTeamsSignInState)
                .where(col(MicrosoftTeamsSignInState.key) == _key(pending_id))
                .returning(col(MicrosoftTeamsSignInState.value))
            )
        ).scalar_one_or_none()
        await session.commit()
    return PendingQuestion.model_validate(value) if value else None
