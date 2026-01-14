from typing import TYPE_CHECKING, Optional, List
import contextvars
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from lib.models.footnote_item import FootnoteItem
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
    footnotes: Optional[List[FootnoteItem]] = Field(
        default=None,
        description="List of footnotes available for lookup by citation detector tools.",
    )


# Context variable for progress tracking (thread-safe for async)
# This is used instead of storing on ContextSchema because contextvars
# are properly scoped for async task execution
current_progress_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar(
    "current_progress_id",
    default=None,
)
