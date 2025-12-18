from typing import List, Type

from langgraph.graph import StateGraph

from lib.models.file import FileRole
from lib.workflows.claim_substantiation.graph import build_claim_substantiator_graph
from lib.workflows.claim_substantiation.issue_converter import convert_state_to_issues
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SubstantiationWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState


class ClaimSubstantiationManifest(
    WorkflowManifest[ClaimSubstantiatorState, SubstantiationWorkflowConfig]
):
    type = WorkflowRunType.CLAIM_SUBSTANTIATION
    name = "Claim Substantiation"
    description = "Extract and verify claims from documents, checking them against supporting documents"
    needs_web_search = False

    def get_state_type(self) -> Type[ClaimSubstantiatorState]:
        """Get the type of the workflow state."""
        return ClaimSubstantiatorState

    def get_config_type(self) -> Type[SubstantiationWorkflowConfig]:
        """Get the type of the workflow config."""
        return SubstantiationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""

        return build_claim_substantiator_graph()

    async def create_initial_state(
        self,
        config: SubstantiationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimSubstantiatorState:
        """Create and return the initial state of the workflow."""

        from lib.services.files import get_files_by_project_id, load_file_document

        project_files = await get_files_by_project_id(config.project_id)
        main_file = next(
            (file for file in project_files if file.role == FileRole.MAIN),
            None,
        )
        supporting_files = [
            file for file in project_files if file.role == FileRole.SUPPORT
        ]
        main_file_document = await load_file_document(main_file)
        supporting_file_documents = [
            await load_file_document(file) for file in supporting_files
        ]

        return ClaimSubstantiatorState(
            file=main_file_document,
            supporting_files=supporting_file_documents,
            config=config,
        )

    def convert_state_to_issues(
        self, state: ClaimSubstantiatorState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert ClaimSubstantiatorState to issues."""
        return convert_state_to_issues(state, claim_state)
