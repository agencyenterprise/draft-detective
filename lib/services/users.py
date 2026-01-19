from typing import List

from fastapi import HTTPException

from lib.config.database import get_db
from lib.models.user import User, UserRole


async def get_or_create_user_by_email(email: str, name: str) -> User:
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            user = User(email=email, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user


async def get_all_users() -> List[User]:
    """Get all users (admin only)."""
    with get_db() as db:
        return db.query(User).order_by(User.created_at.desc()).all()


async def update_user_role(user_id: str, role: UserRole) -> User:
    """Update a user's role."""
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.role = role
        db.commit()
        db.refresh(user)
        return user
