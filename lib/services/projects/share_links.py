"""Service for managing shareable links for read-only access to resources."""

import logging
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Select, select, update
from sqlmodel import col

from lib.config.database import get_async_db_session
from lib.config.env import config
from lib.models.project import Project
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
    share_link: ShareLinkResponse | None = Field(
        default=None, description="Share link details if enabled"
    )


def build_share_url(token: str, anchor: str | None = None) -> str:
    """Build the full shareable URL from a token with optional anchor."""
    base_url = config.FRONTEND_URL or "http://localhost:3000"
    url = f"{base_url}/share/{token}"
    return f"{url}{anchor}" if anchor else url


def _to_response(share_link: ShareLink) -> ShareLinkResponse:
    """Convert a ShareLink to a response model."""
    return ShareLinkResponse(
        token=share_link.token,
        url=build_share_url(share_link.token),
        is_active=share_link.is_active,
    )


def _active_link_query(project_id: uuid.UUID) -> Select[tuple[ShareLink]]:
    return select(ShareLink).where(
        col(ShareLink.project_id) == project_id,
        col(ShareLink.is_active).is_(True),
    )


async def get_active_share_link(project_id: uuid.UUID) -> ShareLink | None:
    """Get the active share link of a project if it exists."""
    async with get_async_db_session() as session:
        result = await session.execute(_active_link_query(project_id))
        return result.scalar_one_or_none()


async def get_resource_by_token(token: str) -> ShareLink | None:
    """Get the share link of a token. Returns None if it is invalid or inactive."""
    async with get_async_db_session() as session:
        stmt = select(ShareLink).where(
            col(ShareLink.token) == token, col(ShareLink.is_active).is_(True)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def enable_sharing(project_id: uuid.UUID, user: User) -> ShareStatusResponse:
    """Enable sharing for a project. Returns its active link or creates one."""
    existing = await get_active_share_link(project_id)
    if existing:
        return ShareStatusResponse(enabled=True, share_link=_to_response(existing))

    async with get_async_db_session() as session:
        # Lock the project row so concurrent enables (a double-click) wait here
        # and find the link the first one created instead of adding a second.
        await session.execute(
            select(col(Project.id))
            .where(col(Project.id) == project_id)
            .with_for_update()
        )
        existing = (
            await session.execute(_active_link_query(project_id))
        ).scalar_one_or_none()
        if existing:
            return ShareStatusResponse(enabled=True, share_link=_to_response(existing))

        share_link = ShareLink(project_id=project_id, created_by_user_id=user.id)
        session.add(share_link)
        await session.commit()
        await session.refresh(share_link)

        logger.info(f"Created share link for project {project_id}: {share_link.token}")
        return ShareStatusResponse(enabled=True, share_link=_to_response(share_link))


async def disable_sharing(project_id: uuid.UUID) -> ShareStatusResponse:
    """Disable ALL active sharing for a project."""
    async with get_async_db_session() as session:
        # Deactivate ALL active links (fixes potential orphaned links)
        stmt = (
            update(ShareLink)
            .where(
                col(ShareLink.project_id) == project_id,
                col(ShareLink.is_active).is_(True),
            )
            .values(is_active=False)
        )
        result = await session.execute(stmt)
        updated = result.rowcount
        await session.commit()

        if updated:
            logger.info(f"Disabled {updated} share link(s) for project {project_id}")

    return ShareStatusResponse(enabled=False, share_link=None)


async def get_share_status(project_id: uuid.UUID) -> ShareStatusResponse:
    """Get the current share status of a project."""
    share_link = await get_active_share_link(project_id)

    if share_link:
        return ShareStatusResponse(enabled=True, share_link=_to_response(share_link))
    return ShareStatusResponse(enabled=False, share_link=None)
