from lib.config.database import get_db
from lib.models.user import User


async def get_or_create_user_by_email(email: str, name: str) -> User:
    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            user = User(email=email, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
