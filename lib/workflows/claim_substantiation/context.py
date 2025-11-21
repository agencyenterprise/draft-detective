from typing import Optional

from lib.services.vector_store import VectorStoreService
from pydantic import BaseModel, ConfigDict, Field


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
