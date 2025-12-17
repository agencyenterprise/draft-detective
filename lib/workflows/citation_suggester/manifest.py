from typing import List, Set, Type

from langgraph.graph import StateGraph

from lib.agents.citation_suggester import RecommendedAction
from lib.workflows.citation_suggester.graph import build_citation_suggester_graph
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentIssue,
    SeverityEnum,
)
from lib.workflows.literature_review.state import LiteratureReviewState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type, get_state_by_type_or_raise


class CitationSuggesterManifest(
    WorkflowManifest[CitationSuggesterState, CitationSuggesterWorkflowConfig]
):
    type = WorkflowRunType.CITATION_SUGGESTER
    name = "Citation Suggester"
    description = "Suggest citations for claims that need additional references. Uses the supporting files plus the literature review analysis results for suggestions, whatever is available."
    needs_web_search = False
    required_dependencies = [
        WorkflowRunType.CLAIM_SUBSTANTIATION,
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

        claim_workflow_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        # Get literature review if available (optional)
        literature_review_state: LiteratureReviewState | None = get_state_by_type(
            WorkflowRunType.LITERATURE_REVIEW, existing_states
        )

        return CitationSuggesterState(
            config=config,
            file=claim_workflow_state.file,
            references=claim_workflow_state.references,
            chunks=claim_workflow_state.chunks,
            supporting_files=claim_workflow_state.supporting_files,
            supporting_documents_summaries=claim_workflow_state.supporting_documents_summaries,
            literature_review=(
                literature_review_state.literature_review
                if literature_review_state
                else None
            ),
        )

    def convert_state_to_issues(
        self, state: CitationSuggesterState, claim_state: ClaimSubstantiatorState
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
                        chunk_index=suggestion.chunk_index,
                        claim_index=suggestion.claim_index,
                    )
                )

        return issues


# Actionable citation actions that warrant an issue
ACTIONABLE_CITATION_ACTIONS: Set[RecommendedAction] = {
    RecommendedAction.ADD_NEW_CITATION,
    RecommendedAction.REPLACE_EXISTING_REFERENCE,
    RecommendedAction.CITE_EXISTING_REFERENCE_IN_NEW_PLACE,
}
