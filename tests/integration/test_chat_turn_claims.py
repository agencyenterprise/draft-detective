"""The claim on a /chat thread while a turn runs, on the real database (``turn_claims``)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.chat_thread import STALE_TURN, ChatThread
from lib.models.conversation import Conversation
from lib.models.user import User
from lib.services import chat_thread_service
from lib.services.chat import turn_claims


@pytest_asyncio.fixture
async def thread() -> AsyncIterator[ChatThread]:
    async with get_async_db_session() as session:
        user = User(
            email=f"turn-claims-{uuid.uuid4().hex[:12]}@example.com", name="Turn Claims"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    created = await chat_thread_service.create_thread(user=user)
    yield created
    async with get_async_db_session() as session:
        await session.execute(
            delete(Conversation).where(col(Conversation.user_id) == user.id)
        )
        await session.execute(delete(User).where(col(User.id) == user.id))
        await session.commit()


async def _reload(thread_id: uuid.UUID) -> ChatThread:
    async with get_async_db_session() as session:
        row = await session.get(ChatThread, thread_id, populate_existing=True)
        assert row is not None
        return row


@pytest.mark.asyncio
async def test_one_turn_at_a_time_and_running_shows_on_the_thread(
    thread: ChatThread,
) -> None:
    assert not (await _reload(thread.id)).is_running
    token = await turn_claims.claim(thread.id)
    assert token is not None
    assert (await _reload(thread.id)).is_running
    assert await turn_claims.claim(thread.id) is None

    await turn_claims.release(thread.id, token)
    assert not (await _reload(thread.id)).is_running
    assert await turn_claims.claim(thread.id) is not None


@pytest.mark.asyncio
async def test_claim_writes_leave_the_threads_place_in_the_list(
    thread: ChatThread,
) -> None:
    before = (await _reload(thread.id)).last_updated_at
    token = await turn_claims.claim(thread.id)
    assert token is not None
    await turn_claims.keep(thread.id, token)
    await turn_claims.release(thread.id, token)
    assert (await _reload(thread.id)).last_updated_at == before


@pytest.mark.asyncio
async def test_a_cancel_request_reaches_the_running_turn(thread: ChatThread) -> None:
    assert not await turn_claims.request_cancel(thread.id)
    token = await turn_claims.claim(thread.id)
    assert token is not None
    assert await turn_claims.keep(thread.id, token)

    assert await turn_claims.request_cancel(thread.id)
    assert not await turn_claims.keep(thread.id, token)

    # The next turn starts without the old request.
    await turn_claims.release(thread.id, token)
    next_token = await turn_claims.claim(thread.id)
    assert next_token is not None
    assert await turn_claims.keep(thread.id, next_token)


@pytest.mark.asyncio
async def test_a_dead_turns_claim_goes_stale_and_it_cannot_free_its_successor(
    thread: ChatThread,
) -> None:
    token = await turn_claims.claim(thread.id)
    assert token is not None
    # A worker that died mid-turn stops stamping its claim.
    async with get_async_db_session() as session:
        await session.execute(
            update(ChatThread)
            .where(col(ChatThread.id) == thread.id)
            .values(turn_seen_at=datetime.now(UTC) - STALE_TURN - timedelta(seconds=1))
        )
        await session.commit()
    assert not (await _reload(thread.id)).is_running

    taken = await turn_claims.claim(thread.id)
    assert taken is not None
    # The stalled turn coming back neither keeps running nor lets go of the new claim.
    assert not await turn_claims.keep(thread.id, token)
    await turn_claims.release(thread.id, token)
    assert await turn_claims.claim(thread.id) is None
    assert await turn_claims.keep(thread.id, taken)
