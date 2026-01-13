from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.citation_suggester import CitationSuggestionResultWithClaimIndex
from lib.agents.literature_review import LiteratureReviewResponse
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class CitationSuggesterWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the citation suggester workflow."""

    type: Literal[WorkflowRunType.CITATION_SUGGESTER] = Field(
        WorkflowRunType.CITATION_SUGGESTER
    )


class CitationSuggesterState(BaseWorkflowState):
    """State for the citation suggester workflow."""

    type: Literal[WorkflowRunType.CITATION_SUGGESTER] = Field(
        WorkflowRunType.CITATION_SUGGESTER
    )
    config: CitationSuggesterWorkflowConfig
    file_id: str = Field(description="ID of the main document")
    literature_review: Optional[LiteratureReviewResponse] = None
    citation_suggestions: List[CitationSuggestionResultWithClaimIndex] = Field(
        default_factory=list,
        description="Citation suggestions for all chunks and claims",
    )
