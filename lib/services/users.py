from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.models.user import User, UserRole


async def get_or_create_user_by_email(email: str, name: str) -> User:
    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.email) == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(email=email, name=name)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user


async def get_all_users() -> List[User]:
    """Get all users (admin only)."""
    async with get_async_db_session() as session:
        stmt = select(User).order_by(col(User.created_at).desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_user_role(user_id: str, role: UserRole) -> User:
    """Update a user's role."""
    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.id) == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.role = role
        await session.commit()
        await session.refresh(user)
        return user


async def update_user_preferences(user_id: str, show_experimental_features: bool) -> User:
    """Update a user's preferences."""
    with get_db() as db:
        stmt = select(User).where(col(User.id) == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.show_experimental_features = show_experimental_features
        db.commit()
        db.refresh(user)
        return user
