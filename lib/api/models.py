from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, field_validator

from lib.models.user import UserRole
from lib.models.workflow_progress import ProgressLevel
from lib.workflows.models import WorkflowGate, WorkflowRunType


class StartWorkflowResponse(BaseModel):
    """Response model for starting a workflow"""

    project_id: str
    workflow_run_id: str
    type: WorkflowRunType
    message: str


class StartMultipleWorkflowsRequest(BaseModel):
    """Request model for starting multiple workflows"""

    project_id: str
    workflow_types: List[WorkflowRunType]
    openai_api_key: str | None = None


class StartMultipleWorkflowsResponse(BaseModel):
    """Response model for starting multiple workflows"""

    project_id: str
    types: List[WorkflowRunType]
    workflow_run_ids: List[str]
    message: str


class WorkflowProgressResponse(BaseModel):
    """Response model for workflow progress entries."""

    id: str
    workflow_run_id: str
    name: str
    level: ProgressLevel
    current_step: int
    total_steps: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "workflow_run_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: Any) -> str:
        """Convert UUID to string for model_validate compatibility."""
        if isinstance(v, UUID):
            return str(v)
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> str:
        """Derive status from timestamps."""
        if self.completed_at:
            return "completed"
        if self.started_at:
            return "in_progress"
        return "pending"

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """Response model for user information"""

    id: str
    email: str
    name: str
    role: UserRole
    show_experimental_features: bool
    has_openai_api_key: bool = False

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: Any) -> str:
        """Convert UUID to string for model_validate compatibility."""
        if isinstance(v, UUID):
            return str(v)
        return v

    model_config = {"from_attributes": True}


class UpdateUserRoleRequest(BaseModel):
    """Request model for updating a user's role"""

    role: UserRole


class UpdateUserPreferencesRequest(BaseModel):
    """Request model for updating user preferences"""

    show_experimental_features: bool


class SetApiKeyRequest(BaseModel):
    """Request model for setting a user's OpenAI API key"""

    openai_api_key: str


class ApproveGateResponse(BaseModel):
    """Response for approving a workflow gate on a project's current revision."""

    gate: WorkflowGate
    revision: int
    released_workflow_run_ids: List[str] = Field(
        description="Runs that were awaiting this gate and have now been scheduled"
    )


class CancelWorkflowResponse(BaseModel):
    """Response for workflow cancellation."""

    message: str
    workflow_run_id: str


class CreateRevisionResponse(BaseModel):
    """Response for creating a new project revision."""

    revision: int
    previous_workflow_types: List[WorkflowRunType]


class RevisionListItem(BaseModel):
    """Summary of a single project revision."""

    revision: int
    main_file_name: str | None = None
    main_file_id: str | None = None
    created_at: datetime | None = None


class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""

    title: str


class LinkReferenceFileRequest(BaseModel):
    """Request body for linking an already-uploaded file to a reference."""

    file_id: str = Field(description="ID of the supporting file to link.")


class LinkReferenceFileResponse(BaseModel):
    """Result of linking a supporting file to a reference."""

    reference_id: str
    file_id: str
