import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class FileRole(str, Enum):
    """Extensible enum for file purposes in workflows"""

    MAIN = "main"
    SUPPORT = "support"
    SUPPORTING_CANDIDATE = "supporting_candidate"


class File(SQLModel, table=True):
    __tablename__ = "files"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the file",
    )
    project_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The project this file belongs to",
    )
    file_name: str = Field(
        sa_column=Column(String, nullable=False),
        description="The original name of the uploaded file",
    )
    file_path: str = Field(
        sa_column=Column(String, nullable=False),
        description="The path to the file in the file system (xxhash-based)",
    )
    file_type: str = Field(
        sa_column=Column(String, nullable=False),
        description="The MIME type of the file",
    )
    file_size: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="The size of the file in bytes",
    )
    content_hash: str = Field(
        sa_column=Column(String, nullable=False, index=True),
        description="xxhash of file content for deduplication",
    )
    original_file_path: str | None = Field(
        sa_column=Column(String, nullable=True),
        description="Path to original file if converted (e.g., .docx before PDF conversion)",
        default=None,
    )
    role: FileRole = Field(
        sa_column=Column(String, nullable=False),
        description="The role of the file in the workflow (main, support, etc.)",
    )
    uploaded_by: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description="The user who uploaded the file",
    )
    description: str | None = Field(
        sa_column=Column(String, nullable=True),
        description="Optional description of the file",
        default=None,
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            nullable=False,
        ),
        description="The timestamp when the file was uploaded",
    )
