from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.literature_review.graph import build_literature_review_graph
from lib.workflows.literature_review.state import (
    LiteratureReviewState,
    LiteratureReviewWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, WorkflowRunType
from lib.workflows.workflow_types import WorkflowState
from lib.workflows.util import get_main_file_id


class LiteratureReviewManifest(
    WorkflowManifest[LiteratureReviewState, LiteratureReviewWorkflowConfig]
):
    type = WorkflowRunType.LITERATURE_REVIEW
    name = "Literature Review"
    description = "Discovers new references by searching the web for relevant academic sources and publications related to your document's claims. Useful for finding papers you may not have cited yet."
    needs_web_search = True
    is_experimental = True
    order = 6
    required_dependencies = [
        WorkflowRunType.REFERENCE_EXTRACTION,
    ]

    def get_state_type(self) -> Type[LiteratureReviewState]:
        """Get the type of the workflow state."""
        return LiteratureReviewState

    def get_config_type(self) -> Type[LiteratureReviewWorkflowConfig]:
        """Get the type of the workflow config."""
        return LiteratureReviewWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_literature_review_graph()

    async def create_initial_state(
        self,
        config: LiteratureReviewWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> LiteratureReviewState:
        """Create and return the initial state of the workflow."""

        return LiteratureReviewState(
            type=WorkflowRunType.LITERATURE_REVIEW,
            config=config,
            file_id=get_main_file_id(existing_states),
        )

    def convert_state_to_issues(
        self, state: LiteratureReviewState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert LiteratureReviewState to issues."""
        return []
