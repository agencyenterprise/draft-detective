from typing import List, Optional, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.issue_converter import _find_chunk_index_by_text
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SeverityEnum,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_validation.graph import build_reference_validation_graph
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class ReferenceValidationManifest(
    WorkflowManifest[ReferenceValidationState, ReferenceValidationWorkflowConfig]
):
    type = WorkflowRunType.REFERENCE_VALIDATION
    name = "Reference Validation"
    description = "Validate each reference from the document by checking if it has an online presence, using web search."
    needs_web_search = True
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

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

        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION,
            existing_states,
        )

        return ReferenceValidationState(
            config=config,
            references=claim_state.references,
        )

    def convert_state_to_issues(
        self, state: ReferenceValidationState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert ReferenceValidationState to issues."""
        issues: List[DocumentIssue] = []

        # Reference Validation: Invalid references
        for validation in state.reference_validations:
            if not validation.valid_reference:
                # Try to find chunk_index from claim_state if available
                chunk_index: Optional[int] = None
                if claim_state:
                    chunk_index = _find_chunk_index_by_text(
                        claim_state, validation.original_reference
                    )

                issue = DocumentIssue(
                    title="Invalid reference",
                    description=f'Possible invalid reference: "{validation.original_reference}"',
                    severity=SeverityEnum.HIGH,
                    chunk_index=chunk_index,
                )
                issues.append(issue)

        return issues
