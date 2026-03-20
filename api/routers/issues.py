"""
Issues API endpoints.

Provides RESTful API for managing persisted issues (resolve/unresolve).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from api.auth import get_current_user
from lib.models.issue import Issue, IssueStatus
from lib.models.project import AccessLevel
from lib.models.user import User
from lib.services.issue_persistence import (
    get_issue_by_id,
    resolve_issue,
    unresolve_issue,
)
from lib.services.projects import get_project_access

router = APIRouter(tags=["issues"])


async def _get_verified_issue(
    issue_id: UUID, user: User, required_level: AccessLevel = AccessLevel.READ
) -> Issue:
    """Fetch an issue and verify the current user has sufficient access to its project."""
    issue = await get_issue_by_id(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    await get_project_access(
        str(issue.project_id), user=user, required_level=required_level
    )
    return issue


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
    chunk_indices: list[int] | None
    status: IssueStatus
    resolved_by: UUID | None
    resolved_at: str | None
    created_at: str
    updated_at: str

    @field_validator("severity", "workflow_type", mode="before")
    @classmethod
    def _extract_enum_value(cls, v: object) -> str:
        """Extract .value from enums; pass strings through."""
        return v.value if hasattr(v, "value") else str(v)

    @field_validator("resolved_at", "created_at", "updated_at", mode="before")
    @classmethod
    def _datetime_to_iso(cls, v: object) -> str | None:
        """Convert datetime objects to ISO-format strings."""
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    @classmethod
    def from_model(cls, issue: Issue) -> "IssueResponse":
        """Convert from Issue model using Pydantic model_validate."""
        return cls.model_validate(issue, from_attributes=True)


@router.post("/api/issues/{issue_id}/resolve", response_model=IssueResponse)
async def resolve_issue_endpoint(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Mark an issue as resolved."""
    await _get_verified_issue(issue_id, current_user, required_level=AccessLevel.WRITE)
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
    await _get_verified_issue(issue_id, current_user, required_level=AccessLevel.WRITE)
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
    issue = await _get_verified_issue(issue_id, current_user)
    return IssueResponse.from_model(issue)
