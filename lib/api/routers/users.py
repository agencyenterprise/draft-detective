"""
User-related API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, Query

from lib.api.auth import get_current_user, require_admin
from lib.api.models import UpdateUserPreferencesRequest, UpdateUserRoleRequest, UserResponse
from lib.models.user import User, UserRole
from lib.services.users import get_all_users, update_user_preferences, update_user_role

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's information."""
    return UserResponse.model_validate(user)


@router.get("", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    search: str | None = Query(
        default=None, description="Filter users by name or email"
    ),
    role: UserRole | None = Query(default=None, description="Filter users by role"),
    limit: int = Query(
        default=20, ge=1, le=100, description="Maximum number of users to return"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of users to skip for pagination"
    ),
) -> List[UserResponse]:
    """List users (admin only), optionally filtered by name, email, or role."""
    users = await get_all_users(search=search, role=role, limit=limit, offset=offset)
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


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    request: UpdateUserPreferencesRequest,
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Update the current user's preferences."""
    updated_user = await update_user_preferences(
        str(user.id), request.show_experimental_features
    )
    return UserResponse.model_validate(updated_user)
