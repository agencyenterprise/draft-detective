"""Manifest for reference file matching workflow."""

from typing import List, Type, cast

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_file_matching.graph import (
    build_reference_file_matching_graph,
)
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
)
from lib.workflows.workflow_types import WorkflowState
from lib.services.files import get_main_file_id, get_processed_supporting_file_ids
from lib.workflows.util import get_state_by_type


class ReferenceFileMatchingManifest(
    WorkflowManifest[ReferenceFileMatchingState, ReferenceFileMatchingConfig]
):
    """Manifest for reference file matching workflow."""

    type = WorkflowRunType.REFERENCE_FILE_MATCHING
    name = "Reference File Matching"
    description = "Match extracted references to supporting documents"
    needs_web_search = False
    is_internal = True
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
        revision: int,
        prior_self_state: ReferenceFileMatchingState | None = None,
    ) -> ReferenceFileMatchingState:
        """
        Create the initial state for a matching run.

        The main file id and the processed supporting file ids are read from
        the file table. Existing matches are carried over from the prior
        matching state so already-matched references are not re-processed.
        """
        existing_matching_state = get_state_by_type(
            WorkflowRunType.REFERENCE_FILE_MATCHING, existing_states
        )
        existing_matches = (
            cast(ReferenceFileMatchingState, existing_matching_state).matches
            if existing_matching_state is not None
            else []
        )

        return ReferenceFileMatchingState(
            type=WorkflowRunType.REFERENCE_FILE_MATCHING,
            config=config,
            file_id=await get_main_file_id(config.project_id, revision),
            supporting_file_ids=await get_processed_supporting_file_ids(
                config.project_id, revision
            ),
            matches=existing_matches,
        )

    def convert_state_to_issues(
        self,
        state: ReferenceFileMatchingState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Reference file matching does not report issues."""

        return []
