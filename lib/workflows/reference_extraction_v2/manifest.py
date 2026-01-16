"""Manifest for reference extraction v2 workflow."""

from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.reference_extraction_v2.graph import (
    build_reference_extraction_v2_graph,
)
from lib.workflows.reference_extraction_v2.state import (
    ReferenceExtractionV2Config,
    ReferenceExtractionV2State,
)
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id


class ReferenceExtractionV2Manifest(
    WorkflowManifest[ReferenceExtractionV2State, ReferenceExtractionV2Config]
):
    """Manifest for reference extraction v2 workflow."""

    type = WorkflowRunType.REFERENCE_EXTRACTION_V2
    name = "Reference Extraction v2"
    description = "Extract bibliographic references using an AI agent with document search capabilities"
    needs_web_search = False
    is_internal = False
    can_be_triggered_by_user = True
    is_experimental = True
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]

    def get_state_type(self) -> Type[ReferenceExtractionV2State]:
        """Get the type of the workflow state."""
        return ReferenceExtractionV2State

    def get_config_type(self) -> Type[ReferenceExtractionV2Config]:
        """Get the type of the workflow config."""
        return ReferenceExtractionV2Config

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_reference_extraction_v2_graph()

    async def create_initial_state(
        self,
        config: ReferenceExtractionV2Config,
        existing_states: List[WorkflowState],
    ) -> ReferenceExtractionV2State:
        """
        Create initial state from DOCUMENT_PROCESSING dependency.

        Gets file with markdown from DOCUMENT_PROCESSING workflow.
        """
        return ReferenceExtractionV2State(
            type=WorkflowRunType.REFERENCE_EXTRACTION_V2,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self,
        state: ReferenceExtractionV2State,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        """Convert reference extraction v2 state to issues."""
        # This workflow extracts references only, no issues to report
        return []
