from datetime import date
from typing import List, Literal, Optional

from pydantic import Field

from lib.agents.literature_review import LiteratureReviewResponse
from lib.agents.models import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.base import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class LiteratureReviewWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for the literature review workflow."""

    type: Literal[WorkflowRunType.LITERATURE_REVIEW] = Field(
        WorkflowRunType.LITERATURE_REVIEW
    )
    document_publication_date: date = Field(
        description="Publication date (YYYY-MM-DD) of the document for literature review. Must be provided. Only references before this date will be considered.",
    )


class LiteratureReviewState(BaseWorkflowState):
    """State for the literature review workflow."""

    type: Literal[WorkflowRunType.LITERATURE_REVIEW] = Field(
        WorkflowRunType.LITERATURE_REVIEW
    )
    config: LiteratureReviewWorkflowConfig
    file: FileDocument
    references: List[BibliographyItem] = Field(default_factory=list)
    literature_review: Optional[LiteratureReviewResponse] = Field(default=None)
