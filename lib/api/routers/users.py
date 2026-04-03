"""
User-related API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from lib.api.auth import get_current_user, require_admin
from lib.api.models import (
    SetApiKeyRequest,
    UpdateUserPreferencesRequest,
    UpdateUserRoleRequest,
    UserResponse,
)
from lib.services.preflight.models import PreflightRequest
from lib.services.preflight.service import PreflightValidationService
from lib.models.user import User, UserRole
from lib.services.users import (
    delete_user_openai_api_key,
    get_all_users,
    set_user_openai_api_key,
    update_user_preferences,
    update_user_role,
)

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_response(user: User) -> UserResponse:
    data = UserResponse.model_validate(user)
    data.has_openai_api_key = user.encrypted_openai_api_key is not None
    return data


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    """Get the current authenticated user's information."""
    return _user_response(user)


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
    return [_user_response(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    admin: User = Depends(require_admin),
) -> UserResponse:
    """Update a user's role (admin only)."""
    user = await update_user_role(user_id, request.role)
    return _user_response(user)


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    request: UpdateUserPreferencesRequest,
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Update the current user's preferences."""
    updated_user = await update_user_preferences(
        str(user.id), request.show_experimental_features
    )
    return _user_response(updated_user)


@router.put("/me/api-key", response_model=UserResponse)
async def set_api_key(
    request: SetApiKeyRequest,
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Validate and store an OpenAI API key for the current user."""
    preflight = PreflightValidationService()
    result = await preflight.validate(
        PreflightRequest(openai_api_key=request.openai_api_key)
    )
    if not result.valid:
        messages = [issue.message for issue in result.issues]
        raise HTTPException(status_code=422, detail="; ".join(messages))

    updated_user = await set_user_openai_api_key(
        str(user.id), request.openai_api_key
    )
    return _user_response(updated_user)


@router.delete("/me/api-key", response_model=UserResponse)
async def remove_api_key(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Remove the stored OpenAI API key for the current user."""
    updated_user = await delete_user_openai_api_key(str(user.id))
    return _user_response(updated_user)
