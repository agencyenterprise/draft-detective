import uuid
from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Column, DateTime, Field, SQLModel, String


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    )
    email: str = Field(sa_column=Column(String, nullable=False))
    name: str = Field(sa_column=Column(String, nullable=False))
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
