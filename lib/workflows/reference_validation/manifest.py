from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.agents.reference_validator import ReferenceValidationFinalResult
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_validation.graph import build_reference_validation_graph
from lib.workflows.reference_validation.state import (
    ReferenceValidationState,
    ReferenceValidationStatus,
    ReferenceValidationWorkflowConfig,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type

_FINAL_RESULT_SEVERITY: dict[ReferenceValidationFinalResult, SeverityEnum] = {
    ReferenceValidationFinalResult.VALID: SeverityEnum.NONE,
    ReferenceValidationFinalResult.FOUND_WITH_INCONSISTENCIES: SeverityEnum.MEDIUM,
    ReferenceValidationFinalResult.NOT_FOUND: SeverityEnum.HIGH,
}

_FINAL_RESULT_TITLE: dict[ReferenceValidationFinalResult, str] = {
    ReferenceValidationFinalResult.VALID: "Valid reference",
    ReferenceValidationFinalResult.FOUND_WITH_INCONSISTENCIES: "Reference found with inconsistencies",
    ReferenceValidationFinalResult.NOT_FOUND: "Reference not found",
}


class ReferenceValidationManifest(
    WorkflowManifest[ReferenceValidationState, ReferenceValidationWorkflowConfig]
):
    type = WorkflowRunType.REFERENCE_VALIDATION
    name = "Reference Error Checking"
    description = "Uses web search to check if each reference from the document is available online and matches author, title, year, and publisher against public internet sources. Useful for checking fabricated or hallucinated references."
    needs_web_search = True
    order = 0
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

        # Get reference extraction state to access chunk_indices
        ref_extraction_state = get_state_by_type(
            WorkflowRunType.REFERENCE_EXTRACTION, other_states
        )
        ref_extraction_state = (
            cast(ReferenceExtractionState, ref_extraction_state)
            if ref_extraction_state
            else None
        )

        # Build lookup from reference id to chunk_indices
        ref_to_chunks: dict[str, List[int]] = {}
        if ref_extraction_state:
            for ref in ref_extraction_state.extracted_references:
                ref_to_chunks[ref.id] = ref.chunk_indices

        for validation in state.reference_validations:
            if validation.status != ReferenceValidationStatus.COMPLETED:
                continue

            if validation.validation_result is None:
                continue

            result = validation.validation_result
            chunk_indices = ref_to_chunks.get(validation.reference_id, [])
            severity = _FINAL_RESULT_SEVERITY[result.final_result]
            title = _FINAL_RESULT_TITLE[result.final_result]

            field_validations = "\n\n".join(
                [
                    f"- **{item.category.value.capitalize()}**: {item.problem_type.value.capitalize()}\n\n\t*Current*: {item.current_value or "-"}\n\n\t*Suggested*: {item.suggested_value}"
                    for item in result.bibliography_field_validations
                ]
            )

            issue = DocumentIssue(
                title=title,
                description=f"> {result.original_reference}\n\n{result.suggested_action}",
                severity=severity,
                type=self.type,
                chunk_indices=chunk_indices if chunk_indices else None,
                long_description=f"{f'### Suggested updated reference\n\n> {result.updated_reference}' if result.updated_reference else ''}\n\n### Field validations\n\n{field_validations}\n\n### Reasoning\n\n{result.reasoning}",
            )
            issues.append(issue)

        return issues
