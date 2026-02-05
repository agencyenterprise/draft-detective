from typing import List, Set, Type, cast

from langgraph.graph import StateGraph

from lib.agents.citation_suggester import RecommendedAction
from lib.workflows.citation_suggester.graph import build_citation_suggester_graph
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.literature_review.state import LiteratureReviewState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_main_file_id, get_state_by_type


class CitationSuggesterManifest(
    WorkflowManifest[CitationSuggesterState, CitationSuggesterWorkflowConfig]
):
    type = WorkflowRunType.CITATION_SUGGESTER
    name = "Citation Suggester"
    description = "Identifies claims that would benefit from additional citations and recommends specific references to cite. Uses your uploaded supporting documents as reference sources. Optionally enhanced by Literature Review results if that analysis is also selected."
    needs_web_search = True
    is_experimental = True
    order = 7
    required_dependencies = [
        WorkflowRunType.CLAIM_EXTRACTION,
        WorkflowRunType.CITATION_DETECTION,
        WorkflowRunType.DOCUMENT_SUMMARIZATION,
    ]
    optional_dependencies = [
        WorkflowRunType.LITERATURE_REVIEW,
    ]

    def get_state_type(self) -> Type[CitationSuggesterState]:
        """Get the type of the workflow state."""
        return CitationSuggesterState

    def get_config_type(self) -> Type[CitationSuggesterWorkflowConfig]:
        """Get the type of the workflow config."""
        return CitationSuggesterWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_citation_suggester_graph()

    async def create_initial_state(
        self,
        config: CitationSuggesterWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> CitationSuggesterState:
        """Create and return the initial state of the workflow."""

        # Get literature review if available (optional)
        literature_review_state_raw = get_state_by_type(
            WorkflowRunType.LITERATURE_REVIEW, existing_states
        )
        literature_review_state = (
            cast(LiteratureReviewState, literature_review_state_raw)
            if literature_review_state_raw is not None
            else None
        )

        return CitationSuggesterState(
            type=WorkflowRunType.CITATION_SUGGESTER,
            config=config,
            file_id=get_main_file_id(existing_states),
            literature_review=(
                literature_review_state.literature_review
                if literature_review_state
                else None
            ),
        )

    def convert_state_to_issues(
        self, state: CitationSuggesterState, other_states: List[WorkflowState]
    ) -> List[DocumentIssue]:
        """Convert CitationSuggesterState to issues."""
        issues = []

        for suggestion in state.citation_suggestions:
            actionable_refs = [
                ref
                for ref in (suggestion.relevant_references or [])
                if ref.recommended_action in ACTIONABLE_CITATION_ACTIONS
            ]
            if actionable_refs:
                ref_summary = "\n".join(
                    f"  • {ref.title} ({ref.recommended_action.value})"
                    for ref in actionable_refs[:3]
                )
                issues.append(
                    DocumentIssue(
                        title="Citation Suggestion",
                        description=(
                            f"{suggestion.rationale}\n\n"
                            f"Consider these references:\n{ref_summary}"
                        ),
                        severity=SeverityEnum.LOW,
                        type=self.type,
                        chunk_index=suggestion.chunk_index,
                    )
                )

        return issues


# Actionable citation actions that warrant an issue
ACTIONABLE_CITATION_ACTIONS: Set[RecommendedAction] = {
    RecommendedAction.ADD_NEW_CITATION,
    RecommendedAction.REPLACE_EXISTING_REFERENCE,
    RecommendedAction.CITE_EXISTING_REFERENCE_IN_NEW_PLACE,
}
