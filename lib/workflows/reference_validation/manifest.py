from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.chunk_utils import build_analyzed_chunks, find_chunk_index_by_text
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_validation.graph import build_reference_validation_graph
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationWorkflowConfig,
)
from lib.workflows.types import WorkflowState


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
        """
        Convert ReferenceValidationState to issues.

        By default, reference validation results are stored as metadata on each
        reference entry and displayed in the References tab via the
        ValidationResultsBox component. This keeps the Document Explorer focused
        on actionable issues.

        When show_invalid_references_as_issues is enabled in the config, invalid
        references will also appear as issues in the Document Explorer.
        """
        if not state.config.show_invalid_references_as_issues:
            return []

        issues: List[DocumentIssue] = []
        chunks = build_analyzed_chunks(other_states)

        for validation in state.reference_validations:
            chunk_index = find_chunk_index_by_text(
                chunks, validation.original_reference
            )

            if not validation.valid_reference:
                issue = DocumentIssue(
                    title="Invalid reference",
                    description=f'Possible invalid reference: "{validation.original_reference}"',
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=chunk_index,
                )
                issues.append(issue)

            if validation.cited_url and validation.url != validation.cited_url:
                issue = DocumentIssue(
                    title="URL redirect detected",
                    description=(
                        f"Cited URL redirects to a different location. "
                        f"Cited: {validation.cited_url} → Canonical: {validation.url}"
                    ),
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=chunk_index,
                )
                issues.append(issue)

        return issues
