from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlmodel import col

from lib.config.database import get_db
from lib.models.user import User, UserRole


async def get_or_create_user_by_email(email: str, name: str) -> User:
    with get_db() as db:
        stmt = select(User).where(col(User.email) == email)
        user = db.execute(stmt).scalar_one_or_none()

        if not user:
            user = User(email=email, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user


async def get_all_users() -> List[User]:
    """Get all users (admin only)."""
    with get_db() as db:
        stmt = select(User).order_by(col(User.created_at).desc())
        return list(db.execute(stmt).scalars().all())


async def update_user_role(user_id: str, role: UserRole) -> User:
    """Update a user's role."""
    with get_db() as db:
        stmt = select(User).where(col(User.id) == user_id)
        user = db.execute(stmt).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.role = role
        db.commit()
        db.refresh(user)
        return user
