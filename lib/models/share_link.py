import secrets
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel, String


def generate_share_token() -> str:
    """Generate a URL-safe share token (22 chars, 128+ bits entropy)."""
    return secrets.token_urlsafe(16)


class ShareLink(SQLModel, table=True):
    """Represents a shareable link for read-only access to a resource."""

    __tablename__ = "share_links"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="Unique identifier for the share link",
    )
    token: str = Field(
        sa_column=Column(String(32), unique=True, index=True, nullable=False),
        default_factory=generate_share_token,
        description="URL-safe unique token for accessing the shared resource",
    )

    # Polymorphic reference to any resource
    resource_type: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Type of resource being shared (e.g., 'project')",
    )
    resource_id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), nullable=False, index=True),
        description="ID of the resource being shared",
    )

    # Ownership and management
    created_by_user_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        description="User who created the share link",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the share link is active (can be revoked)",
    )

    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="When the share link was created",
    )
