"""
Issues API endpoints.

Provides RESTful API for managing persisted issues (resolve/unresolve).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from lib.models.issue import Issue, IssueStatus
from lib.models.user import User
from lib.services.issue_persistence import (
    get_issue_by_id,
    resolve_issue,
    unresolve_issue,
)

router = APIRouter(tags=["issues"])


class IssueResponse(BaseModel):
    """Response model for an issue"""

    id: UUID
    project_id: UUID
    workflow_run_id: UUID
    issue_hash: str
    title: str
    description: str
    long_description: str | None
    severity: str
    workflow_type: str
    chunk_index: int | None
    chunk_indices: list[int] | None
    status: IssueStatus
    resolved_by: UUID | None
    resolved_at: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, issue: Issue) -> "IssueResponse":
        """Convert from Issue model"""
        # workflow_type is stored as string in DB (not enum), so handle both cases
        workflow_type = (
            issue.workflow_type.value
            if hasattr(issue.workflow_type, "value")
            else str(issue.workflow_type)
        )
        return cls(
            id=issue.id,
            project_id=issue.project_id,
            workflow_run_id=issue.workflow_run_id,
            issue_hash=issue.issue_hash,
            title=issue.title,
            description=issue.description,
            long_description=issue.long_description,
            severity=issue.severity.value,
            workflow_type=workflow_type,
            chunk_index=issue.chunk_index,
            chunk_indices=issue.chunk_indices,
            status=issue.status,
            resolved_by=issue.resolved_by,
            resolved_at=issue.resolved_at.isoformat() if issue.resolved_at else None,
            created_at=issue.created_at.isoformat(),
            updated_at=issue.updated_at.isoformat(),
        )


@router.post("/api/issues/{issue_id}/resolve", response_model=IssueResponse)
async def resolve_issue_endpoint(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Mark an issue as resolved."""
    issue = await resolve_issue(issue_id, current_user.id)

    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return IssueResponse.from_model(issue)


@router.post("/api/issues/{issue_id}/unresolve", response_model=IssueResponse)
async def unresolve_issue_endpoint(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Mark an issue as unresolved."""
    issue = await unresolve_issue(issue_id)

    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return IssueResponse.from_model(issue)


@router.get("/api/issues/{issue_id}", response_model=IssueResponse)
async def get_issue_endpoint(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Get a single issue by ID."""
    issue = await get_issue_by_id(issue_id)

    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")

    return IssueResponse.from_model(issue)
