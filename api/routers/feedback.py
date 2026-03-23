"""
Feedback API endpoints.

Provides RESTful API for managing user feedback on analysis results.
"""

import csv
import io
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sqlalchemy import select
from sqlmodel import col

from api.auth import get_current_user, require_admin
from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue
from lib.models.project import FeedbackVisibility
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunType
from lib.services import feedback_service

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    """Generic request model for any entity feedback"""

    workflow_run_id: Optional[UUID] = Field(
        default=None,
        description="Workflow run ID (optional if issue_id is provided)",
    )
    entity_path: dict = Field(
        default_factory=dict,
        description="JSONB path identifying the entity",
        examples=[
            {"chunk_index": 0, "claim_index": 1},  # claim
            {"chunk_index": 0},  # chunk
            {"reference_index": 2},  # reference
            {},  # workflow-level or issue-level (when issue_id is set)
        ],
    )
    issue_id: Optional[UUID] = Field(
        default=None,
        description="Issue ID for issue-level feedback (preferred, derives workflow_run_id automatically)",
    )
    feedback_type: str  # Accept as string, convert in endpoint
    feedback_text: Optional[str] = Field(
        default=None,
        description="Optional feedback text (typically used with thumbs down)",
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback"""

    id: UUID
    workflow_run_id: UUID
    entity_path: dict
    issue_id: Optional[UUID]
    feedback_type: FeedbackType
    feedback_text: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, feedback: Feedback) -> "FeedbackResponse":
        """Convert from Feedback model"""
        return cls(
            id=feedback.id,
            workflow_run_id=feedback.workflow_run_id,
            entity_path=feedback.entity_path,
            issue_id=feedback.issue_id,
            feedback_type=feedback.feedback_type,
            feedback_text=feedback.feedback_text,
            created_at=feedback.created_at.isoformat(),
            updated_at=feedback.updated_at.isoformat(),
        )


@router.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """Submit or update feedback for any entity"""
    async with get_async_db_session() as session:
        feedback_type = FeedbackType(request.feedback_type)
        workflow_run_id = request.workflow_run_id

        # If issue_id is provided, derive workflow_run_id from the issue
        if request.issue_id:
            stmt = select(Issue).where(col(Issue.id) == request.issue_id)
            result = await session.execute(stmt)
            issue = result.scalar_one_or_none()
            if issue is None:
                raise HTTPException(status_code=404, detail="Issue not found")
            workflow_run_id = issue.workflow_run_id

        if workflow_run_id is None:
            raise HTTPException(
                status_code=400,
                detail="Either workflow_run_id or issue_id is required",
            )

        feedback = await feedback_service.create_or_update_feedback(
            session=session,
            workflow_run_id=workflow_run_id,
            entity_path=request.entity_path,
            feedback_type=feedback_type,
            user=current_user,
            feedback_text=request.feedback_text,
            issue_id=request.issue_id,
        )

        return FeedbackResponse.from_model(feedback)


@router.get("/api/feedback", response_model=Optional[FeedbackResponse])
async def get_feedback(
    workflow_run_id: Optional[UUID] = None,
    entity_path: Optional[str] = None,  # JSON string, we'll parse it
    issue_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
) -> Optional[FeedbackResponse]:
    """Get feedback for a specific entity or issue

    Examples:
    - GET /api/feedback?workflow_run_id=xxx&entity_path={"chunk_index":0,"claim_index":1}
    - GET /api/feedback?issue_id=xxx
    """
    async with get_async_db_session() as session:
        # Support getting feedback by issue_id or workflow_run_id/entity_path
        if issue_id:
            feedback = await feedback_service.get_feedback_by_issue(
                session=session,
                issue_id=issue_id,
                user=current_user,
            )
        elif workflow_run_id and entity_path:
            parsed_path = json.loads(entity_path)
            feedback = await feedback_service.get_feedback(
                session=session,
                workflow_run_id=workflow_run_id,
                entity_path=parsed_path,
                user=current_user,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either issue_id or both workflow_run_id and entity_path are required",
            )

        if feedback:
            return FeedbackResponse.from_model(feedback)
        return None


@router.get(
    "/api/feedback/workflow/{workflow_run_id}", response_model=list[FeedbackResponse]
)
async def get_workflow_feedback(
    workflow_run_id: UUID, current_user: User = Depends(get_current_user)
) -> list[FeedbackResponse]:
    """Get all feedback for a workflow run"""
    async with get_async_db_session() as session:
        feedbacks = await feedback_service.get_workflow_feedback(
            session=session, workflow_run_id=workflow_run_id, user=current_user
        )

        return [FeedbackResponse.from_model(f) for f in feedbacks]


@router.get("/api/feedback/project/{project_id}", response_model=list[FeedbackResponse])
async def get_project_feedback(
    project_id: UUID, current_user: User = Depends(get_current_user)
) -> list[FeedbackResponse]:
    """Get all issue feedback for a project (single call for all issues)"""
    async with get_async_db_session() as session:
        feedbacks = await feedback_service.get_project_issue_feedback(
            session=session, project_id=project_id, user=current_user
        )

        return [FeedbackResponse.from_model(f) for f in feedbacks]


class AdminFeedbackItem(BaseModel):
    """Feedback item returned to admins, respecting visibility settings."""

    id: UUID
    feedback_type: FeedbackType
    feedback_text: Optional[str]
    created_at: str
    user_id: UUID
    user_name: str
    user_email: str
    project_id: UUID
    project_title: str
    visibility: FeedbackVisibility
    issue: Issue


@router.get("/api/admin/feedbacks", response_model=list[AdminFeedbackItem])
async def get_admin_feedbacks(
    user_id: Optional[UUID] = None,
    workflow_type: Optional[WorkflowRunType] = None,
    feedback_type: Optional[FeedbackType] = None,
    search: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    _admin: User = Depends(require_admin),
) -> list[AdminFeedbackItem]:
    """Get all shared feedback for admin view. Only returns feedback from projects
    where the user has set visibility to issue_only or full_project."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session,
            user_id=user_id,
            workflow_type=workflow_type.value if workflow_type else None,
            feedback_type=feedback_type,
            search=search,
            limit=limit,
            offset=offset,
        )

        return [
            AdminFeedbackItem(
                id=row["feedback"].id,
                feedback_type=row["feedback"].feedback_type,
                feedback_text=row["feedback"].feedback_text,
                created_at=row["feedback"].created_at.isoformat(),
                user_id=row["user"].id,
                user_name=row["user"].name,
                user_email=row["user"].email,
                project_id=row["project"].id,
                project_title=row["project"].title,
                visibility=row["project"].feedback_visibility,
                issue=row["issue"],
            )
            for row in rows
        ]


@router.get("/api/admin/feedbacks/export")
async def export_admin_feedbacks_csv(
    user_id: Optional[UUID] = None,
    workflow_type: Optional[WorkflowRunType] = None,
    feedback_type: Optional[FeedbackType] = None,
    search: Optional[str] = None,
    _admin: User = Depends(require_admin),
) -> StreamingResponse:
    """Export all shared feedback as a CSV file."""
    async with get_async_db_session() as session:
        rows = await feedback_service.get_admin_feedbacks(
            session=session,
            user_id=user_id,
            workflow_type=workflow_type.value if workflow_type else None,
            feedback_type=feedback_type,
            search=search,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Feedback Date",
                "Feedback Type",
                "Feedback Text",
                "User ID",
                "User Name",
                "User Email",
                "Project ID",
                "Project Title",
                "Visibility",
                "Issue ID",
                "Issue Title",
                "Issue Description",
                "Issue Long Description",
                "Issue Severity",
                "Issue Workflow Type",
            ]
        )
        for row in rows:
            issue = row["issue"]
            writer.writerow(
                [
                    row["feedback"].created_at.isoformat(),
                    row["feedback"].feedback_type.value,
                    row["feedback"].feedback_text or "",
                    str(row["user"].id),
                    row["user"].name,
                    row["user"].email,
                    str(row["project"].id),
                    row["project"].title,
                    row["project"].feedback_visibility.value,
                    str(issue.id) if issue else "",
                    issue.title if issue else "",
                    issue.description if issue else "",
                    issue.long_description or "" if issue else "",
                    issue.severity.value if issue else "",
                    issue.workflow_type if issue else "",
                ]
            )

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=feedbacks.csv"},
        )


@router.delete("/api/feedback/{feedback_id}", response_model=dict)
async def delete_feedback(
    feedback_id: UUID, current_user: User = Depends(get_current_user)
) -> dict:
    """Delete feedback by ID"""
    async with get_async_db_session() as session:
        success = await feedback_service.delete_feedback(
            session=session, feedback_id=feedback_id, user=current_user
        )

        if not success:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return {"success": True}
