"""
User-related API endpoints.
"""

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.models import UserResponse
from lib.models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's information."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
    )
