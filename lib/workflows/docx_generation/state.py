"""State and config models for DOCX generation workflow."""

from typing import Literal, Optional, List, Any

from pydantic import Field

from lib.services.docx.manipulator import DocxComment
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class DocxGenerationWorkflowConfig(BaseWorkflowConfig):
    """Config for DOCX generation workflow."""

    type: Literal[WorkflowRunType.DOCX_GENERATION] = WorkflowRunType.DOCX_GENERATION
    claim_substantiation_run_id: str = Field(
        description="Workflow run ID of the claim substantiation run to generate DOCX from"
    )
    share_token: Optional[str] = Field(
        default=None,
        description="Optional share token to include share links in comments",
    )

    @classmethod
    def requires_api_key(cls) -> bool:
        """DOCX generation doesn't use LLMs, only manipulates existing data."""
        return False


class DocxGenerationState(BaseWorkflowState):
    """State for DOCX generation workflow."""

    type: Literal[WorkflowRunType.DOCX_GENERATION] = WorkflowRunType.DOCX_GENERATION
    config: DocxGenerationWorkflowConfig

    # Intermediate artifacts (not exposed in API)
    comments: Optional[List[DocxComment]] = None
    chunks: Optional[List[Any]] = None  # Uses ChunkLike Protocol at runtime
    original_file_path: Optional[str] = None
    base_file_name: Optional[str] = None

    # Outputs
    generated_file_path: Optional[str] = None
    filename: Optional[str] = None
