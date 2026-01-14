from typing import List, Optional, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import find_chunk_index_by_text
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_validation.graph import build_reference_validation_graph
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type


class ReferenceValidationManifest(
    WorkflowManifest[ReferenceValidationState, ReferenceValidationWorkflowConfig]
):
    type = WorkflowRunType.REFERENCE_VALIDATION
    name = "Reference Validation"
    description = "Validate each reference from the document by checking if it has an online presence, using web search."
    needs_web_search = True
    order = 5
    required_dependencies = [WorkflowRunType.REFERENCE_EXTRACTION]

    def get_state_type(self) -> Type[ReferenceValidationState]:
        """Get the type of the workflow state."""
        return ReferenceValidationState

    def get_config_type(self) -> Type[ReferenceValidationWorkflowConfig]:
        """Get the type of the workflow config."""
        return ReferenceValidationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_validation_graph()

    async def create_initial_state(
        self,
        config: ReferenceValidationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ReferenceValidationState:
        """Create and return the initial state of the workflow."""
        return ReferenceValidationState(
            type=WorkflowRunType.REFERENCE_VALIDATION,
            config=config,
        )

    def convert_state_to_issues(
        self, state: ReferenceValidationState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert ReferenceValidationState to issues."""
        issues: List[DocumentIssue] = []

        doc_state = get_state_by_type(WorkflowRunType.DOCUMENT_PROCESSING, other_states)

        # Reference Validation: Invalid references
        for validation in state.reference_validations:
            if not validation.valid_reference:
                # Try to find chunk_index from claim_state if available
                chunk_index: Optional[int] = None
                if doc_state:
                    doc_state_typed = cast(DocumentProcessingState, doc_state)
                    chunk_index = find_chunk_index_by_text(
                        doc_state_typed.chunks, validation.original_reference
                    )

                issue = DocumentIssue(
                    title="Invalid reference",
                    description=f'Possible invalid reference: "{validation.original_reference}"',
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=chunk_index,
                )
                issues.append(issue)

        return issues
