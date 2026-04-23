import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.config.env import config
from lib.models.user import User, UserRole
from lib.services.users import get_or_create_user_by_email

logger = logging.getLogger(__name__)

# Replace with your actual secret key and algorithm from Auth.js configuration
SECRET_KEY = config.AUTH_SECRET
ALGORITHM = "HS512"

oauth2_scheme = HTTPBearer()
oauth2_scheme_optional = HTTPBearer(auto_error=False)


async def _decode_token(credentials: HTTPAuthorizationCredentials) -> Optional[User]:
    """Shared token decode logic."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer="ai-reviewer",
            audience="ai-reviewer-api",
        )
        email = payload.get("email")
        name = payload.get("name")
        if not email or not name:
            return None
        return await get_or_create_user_by_email(email=email, name=name)
    except jwt.ExpiredSignatureError as err:
        logger.warning("Expired token")
        return None
    except jwt.InvalidTokenError as err:
        logger.error(f"Auth failed: {err}", exc_info=True)
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
) -> User:
    """Returns authenticated user or raises 401."""
    user = await _decode_token(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        oauth2_scheme_optional
    ),
) -> Optional[User]:
    """Returns authenticated user or None if auth fails."""
    if not credentials:
        return None
    return await _decode_token(credentials)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Returns authenticated admin user or raises 403."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
