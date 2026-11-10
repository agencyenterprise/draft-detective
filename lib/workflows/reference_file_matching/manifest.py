"""Manifest for reference file matching workflow."""

from langgraph.graph import StateGraph

from lib.services.files.service import (
    get_main_file_id,
    get_processed_supporting_file_ids,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_file_matching.graph import (
    build_reference_file_matching_graph,
)
from lib.workflows.reference_file_matching.state import (
    ReferenceFileMatchingConfig,
    ReferenceFileMatchingState,
    overlay_matches,
)
from lib.workflows.util import get_state_by_type
from lib.workflows.workflow_types import WorkflowState


class ReferenceFileMatchingManifest(
    WorkflowManifest[ReferenceFileMatchingState, ReferenceFileMatchingConfig]
):
    """Manifest for reference file matching workflow."""

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

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_file_matching_graph()

    async def create_initial_state(
        self,
        config: ReferenceFileMatchingConfig,
        existing_states: list[WorkflowState],
        revision: int,
        prior_self_state: ReferenceFileMatchingState | None = None,
    ) -> ReferenceFileMatchingState:
        """
        Create the initial state for a matching run.

        The main file id and the processed supporting file ids are read from
        the file table. Matches are carried over so already-matched references
        are not re-processed: the prior run's, with any link made on this run
        while it waited on top. `existing_states` holds this run's own row
        (the active run of the type), and a link made then landed there.
        """
        own_state = get_state_by_type(ReferenceFileMatchingState, existing_states)
        existing_matches = overlay_matches(
            prior_self_state.matches if prior_self_state is not None else [],
            own_state.matches if own_state is not None else [],
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
        other_states: list[WorkflowState],
    ) -> list[DocumentIssue]:
        """Reference file matching does not report issues."""

        return []
