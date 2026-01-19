"""
User-related API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends

from api.auth import get_current_user, require_admin
from api.models import UpdateUserRoleRequest, UserResponse
from lib.models.user import User
from lib.services.users import get_all_users, update_user_role

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's information."""
    return UserResponse.model_validate(user)


@router.get("", response_model=List[UserResponse])
async def list_users(admin: User = Depends(require_admin)) -> List[UserResponse]:
    """List all users (admin only)."""
    users = await get_all_users()
    return [UserResponse.model_validate(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    admin: User = Depends(require_admin),
) -> UserResponse:
    """Update a user's role (admin only)."""
    user = await update_user_role(user_id, request.role)
    return UserResponse.model_validate(user)
