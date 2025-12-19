from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_downloader.graph import build_reference_downloader_graph
from lib.workflows.reference_downloader.state import (
    ReferenceDownloaderState,
    ReferenceDownloaderWorkflowConfig,
)
from lib.workflows.types import WorkflowState


class ReferenceDownloaderManifest(
    WorkflowManifest[ReferenceDownloaderState, ReferenceDownloaderWorkflowConfig]
):
    type = WorkflowRunType.REFERENCE_DOWNLOADER
    name = "Reference Downloader"
    description = "Download references from the internet"
    needs_web_search = True
    can_be_triggered_by_user = False
    optional_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

    def get_state_type(self) -> Type[ReferenceDownloaderState]:
        """Get the type of the workflow state."""
        return ReferenceDownloaderState

    def get_config_type(self) -> Type[ReferenceDownloaderWorkflowConfig]:
        """Get the type of the workflow config."""
        return ReferenceDownloaderWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_downloader_graph()

    async def create_initial_state(
        self,
        config: ReferenceDownloaderWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ReferenceDownloaderState:
        """Create and return the initial state of the workflow."""
        return ReferenceDownloaderState(config=config)

    def convert_state_to_issues(
        self,
        state: ReferenceDownloaderState,
        claim_state: ClaimSubstantiatorState,
    ) -> List[DocumentIssue]:
        """Convert ReferenceDownloaderState to issues."""
        return []
