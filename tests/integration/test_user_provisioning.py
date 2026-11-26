"""Integration tests for get_or_create_user_by_email under concurrent first requests."""

import asyncio
import uuid

import pytest
from sqlalchemy import delete, func, select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User
from lib.services.users import get_or_create_user_by_email


async def _delete_by_email(email: str) -> None:
    async with get_async_db_session() as session:
        await session.execute(delete(User).where(col(User.email) == email))
        await session.commit()


async def _count_by_email(email: str) -> int:
    async with get_async_db_session() as session:
        stmt = select(func.count()).select_from(User).where(col(User.email) == email)
        return (await session.execute(stmt)).scalar_one()


@pytest.mark.asyncio
async def test_concurrent_first_requests_create_one_user() -> None:
    email = f"provision-{uuid.uuid4().hex[:10]}@example.com"
    try:
        users = await asyncio.gather(
            *(
                get_or_create_user_by_email(email=email, name="New User")
                for _ in range(6)
            )
        )

        assert {user.id for user in users} == {users[0].id}
        assert await _count_by_email(email) == 1
    finally:
        await _delete_by_email(email)


@pytest.mark.asyncio
async def test_existing_user_is_returned_unchanged() -> None:
    email = f"provision-{uuid.uuid4().hex[:10]}@example.com"
    try:
        first = await get_or_create_user_by_email(email=email, name="First Name")
        again = await get_or_create_user_by_email(email=email, name="Other Name")

        assert again.id == first.id
        assert again.name == "First Name"
    finally:
        await _delete_by_email(email)
