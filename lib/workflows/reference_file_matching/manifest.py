"""Manifest for reference file matching workflow."""

from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.reference_file_matching.graph import (
    build_reference_file_matching_graph,
)
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import (
    get_main_file_id,
    get_state_by_type,
    get_supporting_file_ids,
)


class ReferenceFileMatchingManifest(
    WorkflowManifest[ReferenceFileMatchingState, ReferenceFileMatchingConfig]
):
    """Manifest for reference file matching workflow."""

    type = WorkflowRunType.REFERENCE_FILE_MATCHING
    name = "Reference File Matching"
    description = "Match extracted references to supporting documents"
    needs_web_search = False
    is_internal = True  # Runs as dependency, not user-triggered from workflow list
    can_be_triggered_by_user = True  # Can be used as standalone tool
    required_dependencies = [
        # Needs a direct dependency to doc processing to wait for files to be processed, when files are uploaded after project creation
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
        WorkflowRunType.REFERENCE_EXTRACTION,
    ]
    always_run = True  # Always run reference file matching to ensure new files are matched. The workflow matches only new files in subsequent runs, reusing cached results from previous runs.

    def get_state_type(self) -> Type[ReferenceFileMatchingState]:
        """Get the type of the workflow state."""
        return ReferenceFileMatchingState

    def get_config_type(self) -> Type[ReferenceFileMatchingConfig]:
        """Get the type of the workflow config."""
        return ReferenceFileMatchingConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_file_matching_graph()

    async def create_initial_state(
        self,
        config: ReferenceFileMatchingConfig,
        existing_states: List[WorkflowState],
    ) -> ReferenceFileMatchingState:
        """
        Create initial state from REFERENCE_EXTRACTION dependency.

        Gets file IDs from existing workflow states.
        """
        return ReferenceFileMatchingState(
            type=WorkflowRunType.REFERENCE_FILE_MATCHING,
            config=config,
            file_id=get_main_file_id(existing_states),
            supporting_file_ids=get_supporting_file_ids(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ReferenceFileMatchingState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert reference file matching state to issues."""

        issues: List[DocumentIssue] = []

        # Get reference extraction state to access extracted references
        ref_extraction_state = get_state_by_type(
            WorkflowRunType.REFERENCE_EXTRACTION, other_states
        )
        if ref_extraction_state is None:
            return issues

        ref_extraction_state = cast(ReferenceExtractionState, ref_extraction_state)

        # Build set of matched reference IDs
        matched_ref_ids = {match.reference_id for match in state.matches}

        # References without matching supporting documents
        for reference in ref_extraction_state.extracted_references:
            if reference.id not in matched_ref_ids:
                chunk_indices = reference.chunk_indices
                chunk_index = chunk_indices[0] if chunk_indices else None

                issue = DocumentIssue(
                    title="Missing supporting document for reference",
                    description=f'Reference does not have an associated supporting document: "{reference.text}"',
                    severity=SeverityEnum.LOW,
                    chunk_index=chunk_index,
                    chunk_indices=chunk_indices if chunk_indices else None,
                )
                issues.append(issue)

        return issues
