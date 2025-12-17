from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
)
from lib.workflows.literature_review.graph import build_literature_review_graph
from lib.workflows.literature_review.state import (
    LiteratureReviewState,
    LiteratureReviewWorkflowConfig,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class LiteratureReviewManifest(
    WorkflowManifest[LiteratureReviewState, LiteratureReviewWorkflowConfig]
):
    type = WorkflowRunType.LITERATURE_REVIEW
    name = "Literature Review"
    description = "Performs a literature review related to the claims in the document. Performs web search to find new relevant literature, looking only for literature published before the document publication date."
    needs_web_search = True
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

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
        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        return LiteratureReviewState(
            config=config,
            file=claim_state.file,
            references=claim_state.references,
        )

    def convert_state_to_issues(
        self, state: LiteratureReviewState, claim_state: ClaimSubstantiatorState
    ) -> List[DocumentIssue]:
        """Convert LiteratureReviewState to issues."""
        return []
