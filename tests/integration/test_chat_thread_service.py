"""Integration tests for chat_thread_service.

Hits the real Postgres used by the rest of the test suite (same DATABASE_URL),
so the UUID columns behave as they do in production. Verifies per-user scoping
(cross-user access 404s) and thread CRUD. The conversation itself is not in this
table any more: it lives in the LangGraph checkpointer, keyed by the thread id.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User
from lib.services import chat_thread_service as svc


async def _create_user() -> User:
    async with get_async_db_session() as session:
        user = User(
            email=f"chat-test-{uuid.uuid4().hex[:12]}@example.com",
            name="Chat Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _delete_user(user_id: uuid.UUID) -> None:
    # user_id on chat_threads is ON DELETE CASCADE, so removing the user cleans
    # up all of its threads.
    async with get_async_db_session() as session:
        await session.execute(delete(User).where(col(User.id) == user_id))
        await session.commit()


@pytest_asyncio.fixture
async def user():
    created = await _create_user()
    yield created
    await _delete_user(created.id)


@pytest_asyncio.fixture
async def other_user():
    created = await _create_user()
    yield created
    await _delete_user(created.id)


@pytest.mark.asyncio
async def test_list_threads_scoped_to_owner(user, other_user):
    mine_a = await svc.create_thread(user, title="A")
    mine_b = await svc.create_thread(user, title="B")
    await svc.create_thread(other_user, title="theirs")

    threads = await svc.list_threads(user)

    assert {t.id for t in threads} == {mine_a.id, mine_b.id}


@pytest.mark.asyncio
async def test_get_thread_cross_user_raises_404(user, other_user):
    thread = await svc.create_thread(user, title="mine")

    assert (await svc.get_thread(thread.id, user)).id == thread.id

    with pytest.raises(HTTPException) as exc:
        await svc.get_thread(thread.id, other_user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_missing_thread_raises_404(user):
    with pytest.raises(HTTPException) as exc:
        await svc.get_thread(uuid.uuid4(), user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rename_and_archive_persist(user):
    thread = await svc.create_thread(user)

    renamed = await svc.rename_thread(thread.id, user, "New Title")
    assert renamed.title == "New Title"

    archived = await svc.set_archived(thread.id, user, True)
    assert archived.is_archived is True

    reloaded = await svc.get_thread(thread.id, user)
    assert reloaded.title == "New Title"
    assert reloaded.is_archived is True


@pytest.mark.asyncio
async def test_rename_cross_user_raises_404(user, other_user):
    thread = await svc.create_thread(user, title="mine")

    with pytest.raises(HTTPException) as exc:
        await svc.rename_thread(thread.id, other_user, "hijacked")
    assert exc.value.status_code == 404

    assert (await svc.get_thread(thread.id, user)).title == "mine"


@pytest.mark.asyncio
async def test_delete_thread_removes_it(user):
    thread = await svc.create_thread(user)

    await svc.delete_thread(thread.id, user)

    with pytest.raises(HTTPException) as exc:
        await svc.get_thread(thread.id, user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_thread_cross_user_raises_404(user, other_user):
    thread = await svc.create_thread(user)

    with pytest.raises(HTTPException) as exc:
        await svc.delete_thread(thread.id, other_user)
    assert exc.value.status_code == 404

    # Still present for the real owner.
    assert (await svc.get_thread(thread.id, user)).id == thread.id
