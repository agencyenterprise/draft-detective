"""
Feedback API endpoints.

Provides RESTful API for managing user feedback on analysis results.
"""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lib.api.auth import get_current_user, require_admin
from lib.config.database import get_async_db_session
from lib.models.feedback import Feedback, FeedbackType
from lib.models.issue import Issue
from lib.models.project import FeedbackVisibility
from lib.models.user import User
from lib.models.workflow_run import WorkflowRunType
from lib.services import feedback_service

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    """A user's feedback on an issue"""

    issue_id: UUID = Field(description="The issue this feedback is about")
    feedback_type: FeedbackType
    feedback_text: str | None = Field(
        default=None,
        description="Optional feedback text (typically used with thumbs down)",
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback"""

    id: UUID
    workflow_run_id: UUID
    issue_id: UUID
    feedback_type: FeedbackType
    feedback_text: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, feedback: Feedback) -> "FeedbackResponse":
        """Convert from Feedback model"""
        return cls(
            id=feedback.id,
            workflow_run_id=feedback.workflow_run_id,
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
    """Submit or update the current user's feedback on an issue"""
    async with get_async_db_session() as session:
        feedback = await feedback_service.create_or_update_feedback(
            session=session,
            issue_id=request.issue_id,
            feedback_type=request.feedback_type,
            user=current_user,
            feedback_text=request.feedback_text,
        )

        return FeedbackResponse.from_model(feedback)


@router.get("/api/feedback", response_model=FeedbackResponse | None)
async def get_feedback(
    issue_id: UUID,
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse | None:
    """Get the current user's feedback on an issue"""
    async with get_async_db_session() as session:
        feedback = await feedback_service.get_feedback_by_issue(
            session=session,
            issue_id=issue_id,
            user=current_user,
        )

        if feedback:
            return FeedbackResponse.from_model(feedback)
        return None


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
    feedback_text: str | None
    created_at: str
    user_id: UUID
    user_name: str
    user_email: str
    project_id: UUID
    project_title: str
    project_current_revision: int
    revision: int
    visibility: FeedbackVisibility
    issue: Issue


@router.get("/api/admin/feedbacks", response_model=list[AdminFeedbackItem])
async def get_admin_feedbacks(
    user_id: UUID | None = Query(
        default=None, description="Filter results to feedback submitted by this user."
    ),
    workflow_type: WorkflowRunType | None = Query(
        default=None, description="Filter results to a specific analysis workflow type."
    ),
    feedback_type: FeedbackType | None = Query(
        default=None, description="Filter results to thumbs-up or thumbs-down feedback."
    ),
    search: str | None = Query(
        default=None,
        description="Substring search across issue title/description, project title, user name/email, and feedback text. Multiple words are ANDed together.",
        max_length=200,
    ),
    limit: int = Query(
        default=25, ge=1, le=500, description="Maximum number of results to return."
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of results to skip for pagination."
    ),
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
                project_current_revision=row["project"].current_revision,
                revision=row["workflow_run"].revision,
                visibility=row["project"].feedback_visibility,
                issue=row["issue"],
            )
            for row in rows
        ]


@router.get("/api/admin/feedbacks/export")
async def export_admin_feedbacks_csv(
    user_id: UUID | None = Query(
        default=None, description="Filter results to feedback submitted by this user."
    ),
    workflow_type: WorkflowRunType | None = Query(
        default=None, description="Filter results to a specific analysis workflow type."
    ),
    feedback_type: FeedbackType | None = Query(
        default=None, description="Filter results to thumbs-up or thumbs-down feedback."
    ),
    search: str | None = Query(
        default=None,
        description="Substring search across issue title/description, project title, user name/email, and feedback text. Multiple words are ANDed together.",
        max_length=200,
    ),
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
                "Revision",
                "Project Current Revision",
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
                    row["workflow_run"].revision,
                    row["project"].current_revision,
                    row["project"].feedback_visibility.value,
                    str(issue.id),
                    issue.title,
                    issue.description,
                    issue.long_description or "",
                    issue.severity.value,
                    issue.workflow_type,
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
