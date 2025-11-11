import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.config.env import config
from lib.services.users import get_or_create_user_by_email

logger = logging.getLogger(__name__)

# Replace with your actual secret key and algorithm from Auth.js configuration
SECRET_KEY = config.AUTH_SECRET
ALGORITHM = "HS512"

oauth2_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="ai-reviewer-api",
        )
        email: str = payload.get("email")
        name: str = payload.get("name")
        if not email or not name:
            raise credentials_exception
        return await get_or_create_user_by_email(email=email, name=name)
    except jwt.InvalidTokenError as err:
        logger.error(f"Auth failed: {err}", exc_info=True)
        raise credentials_exception
