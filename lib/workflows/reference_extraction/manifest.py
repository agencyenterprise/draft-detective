"""Manifest for reference extraction workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_extraction.graph import build_reference_extraction_graph
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class ReferenceExtractionManifest(
    WorkflowManifest[ReferenceExtractionState, ReferenceExtractionConfig]
):
    """Manifest for reference extraction workflow."""

    type = WorkflowRunType.REFERENCE_EXTRACTION
    name = "Reference Extraction"
    description = "Extract bibliographic references from document using section detection and windowed extraction"
    needs_web_search = False
    is_internal = True  # Runs as dependency, not user-triggered from workflow list
    can_be_triggered_by_user = True  # Can be used as standalone tool
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[ReferenceExtractionState]:
        """Get the type of the workflow state."""
        return ReferenceExtractionState

    def get_config_type(self) -> Type[ReferenceExtractionConfig]:
        """Get the type of the workflow config."""
        return ReferenceExtractionConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_extraction_graph()

    async def create_initial_state(
        self,
        config: ReferenceExtractionConfig,
        existing_states: List[WorkflowState],
    ) -> ReferenceExtractionState:
        """
        Create initial state from DOCUMENT_PROCESSING dependency.

        Gets file with markdown from DOCUMENT_PROCESSING workflow.
        """
        return ReferenceExtractionState(
            type=WorkflowRunType.REFERENCE_EXTRACTION,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ReferenceExtractionState,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Reference extraction does not produce issues directly."""
        return []
