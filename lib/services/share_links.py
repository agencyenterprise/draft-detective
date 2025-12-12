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


def _build_share_url(token: str, anchor: Optional[str] = None) -> str:
    """Build the full shareable URL from a token with optional anchor."""
    base_url = config.FRONTEND_URL or "http://localhost:3000"
    url = f"{base_url}/share/{token}"
    return f"{url}{anchor}" if anchor else url


def _to_response(share_link: ShareLink) -> ShareLinkResponse:
    """Convert a ShareLink to a response model."""
    return ShareLinkResponse(
        token=share_link.token,
        url=_build_share_url(share_link.token),
        is_active=share_link.is_active,
    )


async def get_active_share_link(
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


async def get_resource_by_token(token: str) -> Optional[ShareLink]:
    """Get resource info by share token. Returns None if token is invalid or inactive."""
    with get_db() as db:
        return (
            db.query(ShareLink)
            .filter(ShareLink.token == token, ShareLink.is_active == True)
            .first()
        )


async def enable_sharing(
    resource_type: str, resource_id: uuid.UUID, user: User
) -> ShareStatusResponse:
    """Enable sharing for a resource. Returns existing active link or creates new one."""
    # Check for existing active link
    existing = await get_active_share_link(resource_type, resource_id)
    if existing:
        return ShareStatusResponse(enabled=True, share_link=_to_response(existing))

    # Create new share link
    with get_db() as db:
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
        return ShareStatusResponse(enabled=True, share_link=_to_response(share_link))


async def disable_sharing(
    resource_type: str, resource_id: uuid.UUID
) -> ShareStatusResponse:
    """Disable ALL active sharing for a resource."""
    with get_db() as db:
        # Deactivate ALL active links (fixes potential orphaned links)
        updated = (
            db.query(ShareLink)
            .filter(
                ShareLink.resource_type == resource_type,
                ShareLink.resource_id == resource_id,
                ShareLink.is_active == True,
            )
            .update({"is_active": False})
        )
        db.commit()

        if updated:
            logger.info(
                f"Disabled {updated} share link(s) for {resource_type}/{resource_id}"
            )

    return ShareStatusResponse(enabled=False, share_link=None)


async def get_share_status(
    resource_type: str, resource_id: uuid.UUID
) -> ShareStatusResponse:
    """Get the current share status for a resource."""
    share_link = await get_active_share_link(resource_type, resource_id)

    if share_link:
        return ShareStatusResponse(enabled=True, share_link=_to_response(share_link))
    return ShareStatusResponse(enabled=False, share_link=None)
