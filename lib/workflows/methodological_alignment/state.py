from typing import Literal, Optional

from pydantic import Field

from lib.agents.methodology_comparator import MethodologyComparisonResponse
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class MethodologicalAlignmentState(BaseWorkflowState):
    """State for the methodological alignment workflow"""

    type: Literal[WorkflowRunType.METHODOLOGICAL_ALIGNMENT] = Field(
        WorkflowRunType.METHODOLOGICAL_ALIGNMENT
    )
    file_id: str = Field(
        description="The ID of the main source document",
    )

    methodology_comparison: Optional[MethodologyComparisonResponse] = Field(
        default=None,
        description="Methodology alignment analysis result",
    )


class MethodologicalAlignmentWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the methodological alignment workflow"""

    type: Literal[WorkflowRunType.METHODOLOGICAL_ALIGNMENT] = Field(
        WorkflowRunType.METHODOLOGICAL_ALIGNMENT
    )
