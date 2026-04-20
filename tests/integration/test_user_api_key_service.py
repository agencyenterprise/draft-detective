"""Integration tests for set/delete user OpenAI API key service functions."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User, UserRole
from lib.services.users import (
    delete_user_openai_api_key,
    get_user_decrypted_api_key,
    set_user_openai_api_key,
)


def _make_user(*, email: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        name="Test User",
        role=UserRole.USER,
        show_experimental_features=False,
    )


async def _insert(user: User) -> User:
    async with get_async_db_session() as session:
        session.add(user)
        await session.commit()
    return user


async def _delete(user_id: uuid.UUID) -> None:
    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.id) == user_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()


@pytest_asyncio.fixture
async def db_user():
    tag = str(uuid.uuid4()).replace("-", "")[:10]
    user = await _insert(_make_user(email=f"apikey-{tag}@example.com"))
    yield user
    await _delete(user.id)


@pytest.mark.asyncio
async def test_set_api_key_stores_encrypted_value(db_user):
    plaintext = "sk-test-key-abc123"
    updated = await set_user_openai_api_key(str(db_user.id), plaintext)

    assert updated.encrypted_openai_api_key is not None
    assert updated.encrypted_openai_api_key != plaintext


@pytest.mark.asyncio
async def test_set_api_key_round_trips_through_decrypt(db_user):
    plaintext = "sk-test-key-xyz789"
    updated = await set_user_openai_api_key(str(db_user.id), plaintext)

    assert get_user_decrypted_api_key(updated) == plaintext


@pytest.mark.asyncio
async def test_delete_api_key_clears_stored_key(db_user):
    await set_user_openai_api_key(str(db_user.id), "sk-key-to-delete")
    updated = await delete_user_openai_api_key(str(db_user.id))

    assert updated.encrypted_openai_api_key is None
    assert get_user_decrypted_api_key(updated) is None


@pytest.mark.asyncio
async def test_delete_api_key_when_none_is_idempotent(db_user):
    updated = await delete_user_openai_api_key(str(db_user.id))
    assert updated.encrypted_openai_api_key is None


@pytest.mark.asyncio
async def test_set_api_key_raises_for_unknown_user():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await set_user_openai_api_key(str(uuid.uuid4()), "sk-key")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_api_key_raises_for_unknown_user():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await delete_user_openai_api_key(str(uuid.uuid4()))

    assert exc_info.value.status_code == 404
