from typing import Literal, Optional

from pydantic import Field

from lib.agents.methodology_comparator import MethodologyComparisonResponse
from lib.models.workflow_run import WorkflowRunType
from lib.services.file import FileDocument
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class MethodologicalAlignmentState(BaseWorkflowState):
    """State for the methodological alignment workflow"""

    type: Literal[WorkflowRunType.METHODOLOGICAL_ALIGNMENT] = Field(
        WorkflowRunType.METHODOLOGICAL_ALIGNMENT
    )
    file: FileDocument = Field(
        description="The main source document",
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
