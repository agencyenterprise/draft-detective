from typing import TYPE_CHECKING, Any, Optional

from lib.services.vector_store import VectorStoreService
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from lib.models.footnote_item import FootnoteItem


class ContextSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    openai_api_key: Optional[str] = Field(
        default=None,
        description="The OpenAI API key to use for the workflow execution.",
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
    footnotes: Optional[Any] = Field(
        default=None,
        description="List of footnotes available for lookup by citation detector tools.",
    )
