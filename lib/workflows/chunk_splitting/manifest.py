"""Manifest for chunk splitting workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.chunk_splitting.graph import build_chunk_splitting_graph
from lib.workflows.chunk_splitting.state import (
    ChunkSplittingState,
    ChunkSplittingWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class ChunkSplittingManifest(
    WorkflowManifest[ChunkSplittingState, ChunkSplittingWorkflowConfig]
):
    """Manifest for chunk splitting workflow."""

    type = WorkflowRunType.CHUNK_SPLITTING
    name = "Chunk Splitting"
    description = "Split document markdown into chunks for analysis"
    needs_web_search = False
    can_be_triggered_by_user = False  # This is a dependency workflow
    is_internal = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[ChunkSplittingState]:
        """Get the type of the workflow state."""
        return ChunkSplittingState

    def get_config_type(self) -> Type[ChunkSplittingWorkflowConfig]:
        """Get the type of the workflow config."""
        return ChunkSplittingWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_chunk_splitting_graph()

    async def create_initial_state(
        self,
        config: ChunkSplittingWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ChunkSplittingState:
        """Create initial state from DOCUMENT_PROCESSING dependency."""
        return ChunkSplittingState(
            type=WorkflowRunType.CHUNK_SPLITTING,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ChunkSplittingState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Chunk splitting does not produce issues directly."""
        return []
