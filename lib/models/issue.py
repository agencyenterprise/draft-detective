"""
Issue model for persisting workflow-generated issues.

Issues are created after workflow completion and archived (not deleted)
when a workflow re-runs, preserving history and feedback integrity.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import computed_field
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlmodel import Enum as SQLModelEnum
from sqlmodel import Field, Relationship, SQLModel

from lib.models.issue_edit import IssueEdit, IssueEditRead
from lib.workflows.models import SeverityEnum, WorkflowRunType


class IssueStatus(str, Enum):
    """Status of a persisted issue"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Issue(SQLModel, table=True):
    """
    Persisted issue from workflow analysis.

    Issues are created after workflow completion and linked to the specific
    workflow run and checkpoint that generated them.
    """

    __tablename__ = "issues"

    id: uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        description="Unique identifier for the issue",
    )

    project_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The project this issue belongs to",
    )

    workflow_run_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="The workflow run that created this issue",
    )

    langgraph_checkpoint_id: Optional[str] = Field(
        sa_column=Column(String(255), nullable=True),
        default=None,
        description="LangGraph checkpoint ID for time travel debugging",
    )

    issue_hash: str = Field(
        sa_column=Column(String(64), nullable=False, index=True),
        description="Deterministic hash from DocumentIssue.id for deduplication",
    )

    title: str = Field(
        sa_column=Column(String(500), nullable=False),
        description="The title of the issue",
    )

    description: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Short description of the issue",
    )

    long_description: Optional[str] = Field(
        sa_column=Column(Text, nullable=True),
        default=None,
        description="Detailed description of the issue",
    )

    suggested_action: Optional[str] = Field(
        sa_column=Column(Text, nullable=True),
        default=None,
        description=(
            "Author-facing recommendation describing how to resolve the issue. "
            "Markdown-formatted."
        ),
    )

    severity: SeverityEnum = Field(
        sa_column=Column(SQLModelEnum(SeverityEnum), nullable=False),
        description="The severity of the issue",
    )

    workflow_type: WorkflowRunType = Field(
        sa_column=Column(String(100), nullable=False),
        description="The workflow type that generated this issue",
    )

    chunk_indices: Optional[List[int]] = Field(
        sa_column=Column(ARRAY(Integer), nullable=True),
        default=None,
        description="All chunk indices related to this issue",
    )

    start_line: Optional[int] = Field(
        sa_column=Column(Integer, nullable=True),
        default=None,
        description="1-indexed start line of the issue in the main document markdown",
    )

    end_line: Optional[int] = Field(
        sa_column=Column(Integer, nullable=True),
        default=None,
        description="1-indexed end line of the issue in the main document markdown",
    )

    status: IssueStatus = Field(
        sa_column=Column(
            SQLModelEnum(IssueStatus), nullable=False, default=IssueStatus.ACTIVE
        ),
        default=IssueStatus.ACTIVE,
        description="Current status of the issue (active or archived)",
    )

    revision: int = Field(
        sa_column=Column(Integer, nullable=False, default=1),
        default=1,
        description="The project revision this issue belongs to (denormalized from workflow run)",
    )

    resolved_by: Optional[uuid.UUID] = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        default=None,
        description="User who resolved this issue (null if unresolved)",
    )

    resolved_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="When the issue was resolved",
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), default=datetime.utcnow, nullable=False
        ),
        description="When the issue was created",
    )

    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        ),
        description="When the issue was last updated",
    )

    __table_args__ = (
        Index("ix_issues_project_status", "project_id", "status"),
        Index("ix_issues_workflow_type", "project_id", "workflow_type"),
        Index("ix_issues_project_revision", "project_id", "revision"),
        Index(
            "ix_issues_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_issues_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
        Index(
            "ix_issues_long_description_trgm",
            "long_description",
            postgresql_using="gin",
            postgresql_ops={"long_description": "gin_trgm_ops"},
        ),
    )

    edit_rows: List["IssueEdit"] = Relationship(
        sa_relationship_kwargs={
            "lazy": "selectin",
            "order_by": "IssueEdit.position",
            "cascade": "all, delete-orphan",
        },
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def edits(self) -> List[IssueEditRead]:
        """The issue's proposed edits, in the order the agent proposed them.

        A computed field rather than a plain property so that every payload
        which serializes an `Issue` row directly -- the project detail
        response, the share endpoint, the MCP tools -- publishes the edits
        without restating the schema.
        """
        return [
            IssueEditRead.model_validate(row, from_attributes=True)
            for row in self.edit_rows
        ]

    @property
    def is_resolved(self) -> bool:
        """Check if the issue is resolved."""
        return self.resolved_by is not None

    def __repr__(self):
        resolved = " [RESOLVED]" if self.is_resolved else ""
        return f"<Issue(id={self.id}, title={self.title[:30]}...{resolved})>"
