from typing import List

from fastapi import HTTPException
from sqlalchemy import or_, select
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


async def get_all_users(
    search: str | None = None,
    role: UserRole | None = None,
    limit: int = 20,
    offset: int = 0,
) -> List[User]:
    """Get all users (admin only), optionally filtered by name, email, or role."""
    async with get_async_db_session() as session:
        stmt = select(User)
        if search:
            for term in search.split():
                pattern = f"%{term}%"
                stmt = stmt.where(
                    or_(col(User.name).ilike(pattern), col(User.email).ilike(pattern))
                )
        if role:
            stmt = stmt.where(col(User.role) == role)
        stmt = stmt.order_by(col(User.name)).limit(limit).offset(offset)
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


async def update_user_preferences(
    user_id: str, show_experimental_features: bool
) -> User:
    """Update a user's preferences."""
    async with get_async_db_session() as session:
        stmt = select(User).where(col(User.id) == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.show_experimental_features = show_experimental_features
        await session.commit()
        await session.refresh(user)
        return user
