"""Service for managing shareable links for read-only access to resources."""

import logging
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from lib.config.database import get_db
from lib.config.env import config
from lib.models.share_link import ShareLink
from lib.models.user import User

logger = logging.getLogger(__name__)


class ShareLinkResponse(BaseModel):
    """Response model for share link operations."""

    token: str = Field(description="The share token")
    url: str = Field(description="The full shareable URL")
    is_active: bool = Field(description="Whether the share link is active")


class ShareStatusResponse(BaseModel):
    """Response model for share status check."""

    enabled: bool = Field(description="Whether sharing is enabled")
    share_link: Optional[ShareLinkResponse] = Field(
        default=None, description="Share link details if enabled"
    )


def _build_share_url(token: str) -> str:
    """Build the full shareable URL from a token."""
    base_url = config.FRONTEND_URL or "http://localhost:3000"
    return f"{base_url}/share/{token}"


def _to_response(share_link: ShareLink) -> ShareLinkResponse:
    """Convert a ShareLink to a response model."""
    return ShareLinkResponse(
        token=share_link.token,
        url=_build_share_url(share_link.token),
        is_active=share_link.is_active,
    )


async def get_share_link_for_resource(
    resource_type: str, resource_id: uuid.UUID
) -> Optional[ShareLink]:
    """Get the active share link for a resource if it exists."""
    with get_db() as db:
        return (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == resource_type,
                ShareLink.resource_id == resource_id,
                ShareLink.is_active == True,
            )
            .first()
        )


async def get_or_create_share_link(
    resource_type: str, resource_id: uuid.UUID, user: User
) -> ShareLink:
    """Get existing active share link or create a new one."""
    with get_db() as db:
        # Check for existing active link
        existing = (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == resource_type,
                ShareLink.resource_id == resource_id,
                ShareLink.is_active == True,
            )
            .first()
        )

        if existing:
            return existing

        # Create new share link
        share_link = ShareLink(
            resource_type=resource_type,
            resource_id=resource_id,
            created_by_user_id=user.id,
        )
        db.add(share_link)
        db.commit()
        db.refresh(share_link)

        logger.info(
            f"Created share link for {resource_type}/{resource_id}: {share_link.token}"
        )
        return share_link


async def get_resource_by_token(token: str) -> Optional[ShareLink]:
    """Get resource info by share token. Returns None if token is invalid or inactive."""
    with get_db() as db:
        return (
            db.query(ShareLink)
            .filter(ShareLink.token == token, ShareLink.is_active == True)
            .first()
        )


async def toggle_share_link(
    resource_type: str, resource_id: uuid.UUID, user: User, enable: bool
) -> ShareStatusResponse:
    """Enable or disable sharing for a resource."""
    with get_db() as db:
        existing = (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == resource_type,
                ShareLink.resource_id == resource_id,
            )
            .first()
        )

        if not enable:
            if existing:
                existing.is_active = False
                db.commit()
            return ShareStatusResponse(enabled=False, share_link=None)

        # Enable: reuse existing or create new
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
                return ShareStatusResponse(
                    enabled=True, share_link=_to_response(existing)
                )

            share_link = ShareLink(
                resource_type=resource_type,
                resource_id=resource_id,
                created_by_user_id=user.id,
            )
            db.add(share_link)
            db.commit()
            db.refresh(share_link)
            return ShareStatusResponse(
                enabled=True, share_link=_to_response(share_link)
            )


async def get_share_status(
    resource_type: str, resource_id: uuid.UUID
) -> ShareStatusResponse:
    """Get the current share status for a resource."""
    share_link = await get_share_link_for_resource(resource_type, resource_id)

    if share_link:
        return ShareStatusResponse(enabled=True, share_link=_to_response(share_link))
    return ShareStatusResponse(enabled=False, share_link=None)
