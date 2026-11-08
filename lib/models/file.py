import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class FileRole(str, Enum):
    """Extensible enum for file purposes in workflows"""

    MAIN = "main"
    SUPPORT = "support"
    SUPPORTING_CANDIDATE = "supporting_candidate"
    # Retired upload roles of the former Peer Review tab: a reviewer's memo on
    # a draft, and the author's reply to it. Files that carry them still load,
    # list, and can be handed to the Review Assistant; new uploads are rejected.
    REVIEWER_MEMO = "reviewer_memo"
    RESPONSE_MEMO = "response_memo"
    # Any document the author hands the Review Assistant without saying what it
    # is: a draft, a reviewer memo, a marked-up copy, a response memo. The agent
    # works out which. Shared across revisions, like a supporting document.
    REVIEW_INPUT = "review_input"
    # Derived artifact, not an upload: an image extracted from a document
    # during markdown conversion. Has parent_file_id set when the document is a
    # project's file; an image from a document read in the Word add-in's chat or
    # in Teams has no parent file, only its conversation (conversation_id). Readers must opt in by role —
    # file listings never include these implicitly.
    EXTRACTED_IMAGE = "extracted_image"


# Every role a person uploads, as opposed to the files the app derives or
# fetches (supporting candidates, extracted images). The project's file lists
# and the Review Assistant's inputs read these; a new upload role goes here.
UPLOADED_ROLES: tuple[FileRole, ...] = (
    FileRole.MAIN,
    FileRole.SUPPORT,
    FileRole.REVIEWER_MEMO,
    FileRole.RESPONSE_MEMO,
    FileRole.REVIEW_INPUT,
)


class File(SQLModel, table=True):
    __tablename__ = "files"
    # One MAIN document per (project, revision), enforced at the DB layer so
    # concurrent uploads racing past the application-level check cannot both
    # insert. Partial index: other roles are unconstrained, and MAIN files
    # always carry a revision.
    __table_args__ = (
        Index(
            "uq_files_one_main_per_project_revision",
            "project_id",
            "revision",
            unique=True,
            postgresql_where=text("role = 'main'"),
        ),
        # Every file has exactly one owner: a project, or a conversation (an image of
        # a document read in the Word add-in's chat or in Teams). Whatever reads a
        # file checks it against that owner.
        CheckConstraint(
            "num_nonnulls(project_id, conversation_id) = 1",
            name="ck_files_one_owner",
        ),
    )

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="The unique identifier for the file",
    )
    project_id: uuid.UUID | None = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        default=None,
        description="The project this file belongs to; None for a conversation's",
    )
    conversation_id: uuid.UUID | None = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        default=None,
        description="The conversation this file belongs to, if not a project's",
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
    uploaded_by: uuid.UUID | None = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        default=None,
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

    # Artifact columns for caching processed content
    markdown: str | None = Field(
        sa_column=Column(Text, nullable=True),
        description="Cached markdown conversion of the file",
        default=None,
    )
    summary: dict | None = Field(
        sa_column=Column(JSONB, nullable=True),
        description="Document summary as JSON (DocumentSummary schema)",
        default=None,
    )
    revision: int | None = Field(
        sa_column=Column(Integer, nullable=True, index=True),
        default=None,
        description="Revision number this file belongs to. NULL means shared across all revisions (e.g., supporting docs).",
    )

    # Set for EXTRACTED_IMAGE rows only. Where an image sits in the parent's
    # markdown is not duplicated here: the parent's markdown references the
    # image by id (draftdetective://{id}), so position derives from it.
    parent_file_id: uuid.UUID | None = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("files.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        default=None,
        description="For extracted images: the file this image was extracted from",
    )

    @property
    def has_cached_markdown(self) -> bool:
        """Check if this file has cached markdown content."""
        return self.markdown is not None

    @property
    def has_cached_summary(self) -> bool:
        """Check if this file has a cached summary."""
        return self.summary is not None


class FileListItem(BaseModel):
    """File model for list responses, excluding heavy content fields (markdown, summary)."""

    id: uuid.UUID
    project_id: uuid.UUID
    file_name: str
    file_path: str
    file_type: str
    file_size: int
    content_hash: str
    original_file_path: str | None = None
    role: FileRole
    uploaded_by: uuid.UUID | None = None
    description: str | None = None
    created_at: datetime
    revision: int | None = None
