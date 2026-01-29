from typing import Optional, List
import contextvars
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lib.services.file_artifacts_service.types import FileArtifactsServiceType
from lib.services.vector_store import VectorStoreService


class ContextSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    openai_api_key: Optional[str] = Field(
        default=None,
        description="The OpenAI API key to use for the workflow execution.",
    )
    file_artifacts_service: FileArtifactsServiceType = Field(
        description="The file artifacts service to use for the workflow execution.",
    )
    vector_store: Optional[VectorStoreService] = Field(
        default=None,
        description="The vector store service to use for the workflow execution.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="The ID of the user that is running the workflow.",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="The ID of the project that is running the workflow.",
    )
    workflow_run_id: Optional[str] = Field(
        default=None,
        description="The ID of the workflow run record related to this langgraph thread.",
    )


# Context variable for progress tracking (thread-safe for async)
# This is used instead of storing on ContextSchema because contextvars
# are properly scoped for async task execution
current_progress_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "current_progress_id",
    default=None,
)

# Context variable for workflow run ID (thread-safe for async)
# Used to tag errors with the run they occurred in, enabling filtering
# of errors to only show those from the current run
current_workflow_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_workflow_run_id",
    default=None,
)


def get_current_workflow_run_id() -> Optional[str]:
    """Get the current workflow run ID from context variable."""
    try:
        return current_workflow_run_id.get()
    except Exception:
        return None
