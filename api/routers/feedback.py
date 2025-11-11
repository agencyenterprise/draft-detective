"""
Feedback API endpoints.

Provides RESTful API for managing user feedback on analysis results.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user
from lib.config.database import get_db
from lib.models.feedback import Feedback, FeedbackType
from lib.models.user import User
from lib.services import feedback_service

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    """Generic request model for any entity feedback"""

    workflow_run_id: UUID
    entity_path: dict = Field(
        description="JSONB path identifying the entity",
        examples=[
            {"chunk_index": 0, "claim_index": 1},  # claim
            {"chunk_index": 0},  # chunk
            {"reference_index": 2},  # reference
            {},  # workflow-level
        ],
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
    with get_db() as session:
        feedback_type = FeedbackType(request.feedback_type)

        feedback = feedback_service.create_or_update_feedback(
            session=session,
            workflow_run_id=request.workflow_run_id,
            entity_path=request.entity_path,
            feedback_type=feedback_type,
            user=current_user,
            feedback_text=request.feedback_text,
        )

        return FeedbackResponse.from_model(feedback)


@router.get("/api/feedback", response_model=Optional[FeedbackResponse])
async def get_feedback(
    workflow_run_id: UUID,
    entity_path: str,  # JSON string, we'll parse it
    current_user: User = Depends(get_current_user),
) -> Optional[FeedbackResponse]:
    """Get feedback for a specific entity

    Example: GET /api/feedback?workflow_run_id=xxx&entity_path={"chunk_index":0,"claim_index":1}
    """
    import json

    with get_db() as session:
        parsed_path = json.loads(entity_path)

        feedback = feedback_service.get_feedback(
            session=session,
            workflow_run_id=workflow_run_id,
            entity_path=parsed_path,
            user=current_user,
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
    with get_db() as session:
        feedbacks = feedback_service.get_workflow_feedback(
            session=session, workflow_run_id=workflow_run_id, user=current_user
        )

        return [FeedbackResponse.from_model(f) for f in feedbacks]


@router.delete("/api/feedback/{feedback_id}", response_model=dict)
async def delete_feedback(
    feedback_id: UUID, current_user: User = Depends(get_current_user)
) -> dict:
    """Delete feedback by ID"""
    with get_db() as session:
        success = feedback_service.delete_feedback(
            session=session, feedback_id=feedback_id, user=current_user
        )

        if not success:
            raise HTTPException(status_code=404, detail="Feedback not found")

        return {"success": True}
