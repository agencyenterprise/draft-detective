from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
)
from lib.workflows.docx_generation.graph import build_docx_generation_graph
from lib.workflows.docx_generation.state import (
    DocxGenerationState,
    DocxGenerationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState


class DocxGenerationManifest(
    WorkflowManifest[DocxGenerationState, DocxGenerationWorkflowConfig]
):
    type = WorkflowRunType.DOCX_GENERATION
    name = "DOCX Generation"
    description = "Generate a DOCX file with comments from workflow analysis results"
    needs_web_search = False
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

    def get_state_type(self) -> Type[DocxGenerationState]:
        """Get the type of the workflow state."""
        return DocxGenerationState

    def get_config_type(self) -> Type[DocxGenerationWorkflowConfig]:
        """Get the type of the workflow config."""
        return DocxGenerationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_docx_generation_graph()

    async def create_initial_state(
        self,
        config: DocxGenerationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> DocxGenerationState:
        """Create and return the initial state of the workflow."""
        return DocxGenerationState(config=config)

    def convert_state_to_issues(
        self, state: DocxGenerationState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        # DOCX generation doesn't produce issues directly, but uses issues from other workflows
        return []
