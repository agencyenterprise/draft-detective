import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, Field, SQLModel, String


class AppConfig(SQLModel, table=True):
    __tablename__ = "app_configs"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    key: str = Field(
        sa_column=Column(String, nullable=False, unique=True, index=True),
        description="Stable identifier used in code, e.g. 'about_this_ger.preface_validator.system_prompt'",
    )
    value: str = Field(
        sa_column=Column(Text, nullable=False),
        description="The configuration value (may be long, e.g. a full prompt)",
    )
    description: str = Field(
        sa_column=Column(Text, nullable=False, default=""),
        description="Human-readable explanation shown to admins",
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )
    )
    updated_by: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="The admin who last modified this config",
    )
