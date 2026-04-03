"""Endpoints for managing runtime application configs."""

import logging
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from lib.api.auth import require_admin
from lib.models.user import User
from lib.services.app_configs import (
    delete_config,
    get_all_configs,
    get_config,
    seed_all_defaults,
    upsert_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/app-configs", tags=["app-configs"])


class AppConfigResponse(BaseModel):
    id: str
    key: str
    value: str
    description: str
    updated_at: datetime
    updated_by: Optional[str] = None

    @field_validator("id", "updated_by", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: Any) -> Optional[str]:
        if isinstance(v, UUID):
            return str(v)
        return v

    model_config = {"from_attributes": True}


class AppConfigValueResponse(BaseModel):
    value: str


class UpsertAppConfigRequest(BaseModel):
    value: str
    description: Optional[str] = None


@router.get("", response_model=List[AppConfigResponse])
async def list_app_configs(
    admin: User = Depends(require_admin),
) -> List[AppConfigResponse]:
    """List all application configs."""
    configs = await get_all_configs()
    return [AppConfigResponse.model_validate(c) for c in configs]


@router.get("/{key:path}", response_model=AppConfigValueResponse)
async def get_app_config(
    key: str,
) -> AppConfigValueResponse:
    """Return the value for a single config key. Public endpoint, no auth required."""

    value = await get_config(key)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found",
        )
    return AppConfigValueResponse(value=value)


@router.put("/{key:path}", response_model=AppConfigResponse)
async def update_app_config(
    key: str,
    request: UpsertAppConfigRequest,
    admin: User = Depends(require_admin),
) -> AppConfigResponse:
    """Create or update an application config value."""
    row = await upsert_config(
        key=key,
        value=request.value,
        description=request.description,
        user_id=admin.id,
    )
    return AppConfigResponse.model_validate(row)


@router.delete("/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_app_config(
    key: str,
    admin: User = Depends(require_admin),
) -> None:
    """Delete a config override (resets to code default)."""
    deleted = await delete_config(key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config key '{key}' not found",
        )
    await seed_all_defaults()
