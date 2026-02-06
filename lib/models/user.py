import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, Field, SQLModel, String
from sqlmodel import Enum as SQLModelEnum


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    RAND = "RAND"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    email: str = Field(sa_column=Column(String, nullable=False, unique=True))
    name: str = Field(sa_column=Column(String, nullable=False))
    role: UserRole = Field(
        sa_column=Column(
            SQLModelEnum(UserRole),
            nullable=False,
            default=UserRole.USER,
        ),
        description="The role of the user",
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            nullable=False,
        )
    )
    last_updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )
    )
    show_experimental_features: bool = Field(
        sa_column=Column(Boolean, nullable=False, default=False),
        description="Whether the user has opted into experimental features",
    )
