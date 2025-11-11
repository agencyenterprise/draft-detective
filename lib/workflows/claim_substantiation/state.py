from datetime import date
from enum import StrEnum
from operator import add
from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, Field

# Agent response models
from lib.agents.citation_detector import CitationResponse
from lib.agents.citation_suggester import CitationSuggestionResultWithClaimIndex
from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponse
from lib.agents.claim_needs_substantiation_checker import (
    ClaimCommonKnowledgeResultWithClaimIndex,
)
from lib.agents.claim_verifier import ClaimSubstantiationResultWithClaimIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.evidence_weighter import EvidenceWeighterResponseWithClaimIndex
from lib.agents.inference_validator import InferenceValidationResponseWithClaimIndex
from lib.agents.reference_validator import BibliographyItemValidation
from lib.agents.literature_review import LiteratureReviewResponse
from lib.agents.models import ChunkWithIndex, ClaimCategory
from lib.agents.reference_extractor import BibliographyItem
from lib.agents.toulmin_claim_extractor import ToulminClaimResponse

# Service models
from lib.services.file import FileDocument
from lib.services.docling_models import ChunkToItems

# Workflow models
from lib.workflows.models import WorkflowError
from lib.agents.addendum_generator import Addendum
from lib.agents.addendum_report_generator import ReportOutput


class SubstantiationWorkflowConfig(BaseModel):
    """Configuration model for claim substantiation workflow"""

    use_toulmin: bool = Field(
        default=False, description="Whether to use Toulmin claim detection approach"
    )
    run_literature_review: bool = Field(
        default=False, description="Whether to run the literature review"
    )
    run_suggest_citations: bool = Field(
        default=False, description="Whether to run the citation suggestions"
    )
    use_rag: bool = Field(
        default=True,
        description="Use RAG for claim verification",
    )
    run_live_reports: bool = Field(
        default=False, description="Whether to run the live reports analysis"
    )
    run_reference_validation: bool = Field(
        default=False, description="Whether to validate references using web search"
    )
    document_publication_date: Optional[date] = Field(
        default=None,
        description="Publication date (YYYY-MM-DD) of the document for literature review and live reports",
    )
    target_chunk_indices: Optional[List[int]] = Field(
        default=None,
        description="Specific chunk indices to process (None = process all chunks)",
    )
    agents_to_run: Optional[List[str]] = Field(
        default=None, description="Specific agents to run (None = run all agents)"
    )
    domain: Optional[str] = Field(
        default=None, description="Domain context for more accurate analysis"
    )
    target_audience: Optional[str] = Field(
        default=None, description="Target audience context for analysis"
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for Langfuse tracing"
    )


class DocumentChunkSummary(ChunkWithIndex):
    """Summary chunk info without detailed analysis (for API responses)"""

    has_claims: bool = Field(default=False, description="Whether this chunk has claims")
    claims_count: int = Field(default=0, description="Number of claims in this chunk")
    has_citations: bool = Field(
        default=False, description="Whether this chunk has citations"
    )
    citations_count: int = Field(
        default=0, description="Number of citations in this chunk"
    )


class DocumentChunk(ChunkWithIndex):
    """Independent chunk response object with all processing results"""

    claims: Optional[ClaimResponse | ToulminClaimResponse] = None
    citations: Optional[CitationResponse] = None
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = []
    claim_common_knowledge_results: List[ClaimCommonKnowledgeResultWithClaimIndex] = []
    substantiations: List[ClaimSubstantiationResultWithClaimIndex] = []
    citation_suggestions: List[CitationSuggestionResultWithClaimIndex] = []
    live_reports_analysis: List[EvidenceWeighterResponseWithClaimIndex] = []
    inference_validations: List[InferenceValidationResponseWithClaimIndex] = []

    def to_summary(self) -> DocumentChunkSummary:
        """Convert full chunk to lightweight summary"""
        claims_list = self.claims.claims if self.claims else []
        citations_list = self.citations.citations if self.citations else []

        return DocumentChunkSummary(
            content=self.content,
            chunk_index=self.chunk_index,
            paragraph_index=self.paragraph_index,
            has_claims=len(claims_list) > 0,
            claims_count=len(claims_list),
            has_citations=len(citations_list) > 0,
            citations_count=len(citations_list),
        )


def conciliate_chunks(
    a: List[DocumentChunk], b: List[DocumentChunk]
) -> List[DocumentChunk]:
    """
    Conciliate two lists of DocumentChunk by merging their properties.

    This reducer function is used by LangGraph to handle multiple updates to the same
    chunks field from different nodes running in parallel.

    Args:
        a: First list of DocumentChunk (existing state)
        b: Second list of DocumentChunk (new updates)

    Returns:
        Merged list of DocumentChunk with combined properties
    """

    # Create a dictionary for quick lookup of chunks by index
    chunks_by_index = {chunk.chunk_index: chunk for chunk in a}

    # Merge updates from b into the existing chunks
    for updated_chunk in b:
        if updated_chunk is None:
            # in case chunk processing errored, a None is returned here so we skip the result
            continue

        existing_chunk = chunks_by_index.get(updated_chunk.chunk_index)
        if existing_chunk is None:
            # If chunk doesn't exist in a, add it
            chunks_by_index[updated_chunk.chunk_index] = updated_chunk
        else:
            # Merge the chunks by updating fields that have been updated in the updated chunk
            merged_data = existing_chunk.model_dump()

            # Update fields that have been updated in the updated chunk
            for field, updated_value in updated_chunk.model_dump().items():
                if updated_value is None:
                    # Skip None values - no update has happened
                    continue

                if isinstance(updated_value, list) and not updated_value:
                    # Skip empty lists - no update has happened (empty lists are used as default state values for some fields)
                    continue

                merged_data[field] = updated_value

            # Create the merged chunk
            chunks_by_index[updated_chunk.chunk_index] = DocumentChunk(**merged_data)

    # Return chunks in order by chunk_index
    return [chunks_by_index[i] for i in sorted(chunks_by_index.keys())]


class ClaimCommonKnowledgeResultChunk(BaseModel):
    """
    Wrapper for a list of claim common knowledge results for a single chunk.

    openapi-generator does not support List[List[T]] so we need to wrap the list of substantiations in a single model.
    """

    claim_common_knowledge_results: List[ClaimCommonKnowledgeResultWithClaimIndex]


class ClaimSubstantiationChunk(BaseModel):
    """
    Wrapper for a list of claim substantiation results for a single chunk.

    openapi-generator does not support List[List[T]] so we need to wrap the list of substantiations in a single model.
    """

    substantiations: List[ClaimSubstantiationResultWithClaimIndex]


class SeverityEnum(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    def sort_index(self) -> int:
        return {
            self.NONE: 0,
            self.LOW: 1,
            self.MEDIUM: 2,
            self.HIGH: 3,
        }[self]


class DocumentIssue(BaseModel):
    title: str = Field(description="The title of the issue")
    description: str = Field(description="The description of the issue")
    severity: SeverityEnum = Field(description="The severity of the issue")
    additional_context: Optional[str] = Field(
        description="A longer explanation for the description of the issue and/or context of the issue",
        default=None,
    )
    chunk_index: Optional[int] = Field(
        description="The index of the chunk that contains the issue", default=None
    )
    claim_index: Optional[int] = Field(
        description="The index of the claim that contains the issue", default=None
    )
    claim_category: Optional[ClaimCategory] = Field(
        description="The category of the claim that contains the issue", default=None
    )


class ClaimSubstantiatorState(BaseModel):
    # Inputs
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
    config: SubstantiationWorkflowConfig

    # Outputs
    workflow_run_id: Optional[str] = Field(
        default=None,
        description="The UUID of the workflow run (populated when workflow starts)",
    )
    references: Annotated[List[BibliographyItem], add] = []
    references_validated: Annotated[List[BibliographyItemValidation], add] = []
    chunks: Annotated[List[DocumentChunk], conciliate_chunks] = []
    errors: Annotated[List[WorkflowError], add] = Field(
        default_factory=list,
        description="Errors that occurred during the processing of the document.",
    )
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = Field(
        default=None,
        description="Dictionary mapping supporting file indices to their summaries",
    )
    live_reports_analysis: List[EvidenceWeighterResponseWithClaimIndex] = Field(
        default_factory=list, description="Live reports analysis results by chunk index"
    )
    literature_review: Optional[LiteratureReviewResponse] = None
    addendum: Optional[Addendum] = Field(
        default=None, description="Structured addendum generated from live reports"
    )
    addendum_report: Optional[ReportOutput] = Field(
        default=None, description="Report output from the addendum report generator"
    )
    ranked_issues: List[DocumentIssue] = Field(
        default_factory=list,
        description="Ranked list of document issues with severity levels",
    )
    chunk_to_items: Optional[ChunkToItems] = Field(
        default=None,
        description="Mapping from chunk indices to Docling items/regions for rendering",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[DocumentChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])


class ClaimSubstantiatorStateSummary(BaseModel):
    """Summary version of ClaimSubstantiatorState with chunk summaries instead of full chunks"""

    # Inputs
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
    config: SubstantiationWorkflowConfig

    # Outputs - using lightweight chunks
    workflow_run_id: Optional[str] = None
    references: List[BibliographyItem] = []
    references_validated: List[BibliographyItemValidation] = []
    chunks: List[DocumentChunkSummary] = Field(
        default_factory=list,
        description="Lightweight chunk summaries without detailed analysis",
    )
    errors: List[WorkflowError] = []
    main_document_summary: Optional[DocumentSummary] = None
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = None
    live_reports_analysis: List[EvidenceWeighterResponseWithClaimIndex] = []
    literature_review: Optional[LiteratureReviewResponse] = None
    addendum: Optional[Addendum] = None
    addendum_report: Optional[ReportOutput] = None
    ranked_issues: List[DocumentIssue] = []
    chunk_to_items: Optional[ChunkToItems] = None


class ChunkReevaluationRequest(BaseModel):
    """Request model for re-evaluating a specific chunk"""

    chunk_index: int = Field(
        ge=0, description="Zero-based index of the chunk to re-evaluate"
    )
    agents_to_run: List[str] = Field(
        description="List of agent types to run on the chunk",
    )
    original_state: ClaimSubstantiatorState = Field(
        description="The original workflow state containing the document and chunks"
    )
    session_id: Optional[str] = Field(description="The session ID for Langfuse tracing")


class ChunkReevaluationResponse(BaseModel):
    """Response model for chunk re-evaluation results"""

    state: ClaimSubstantiatorState = Field(
        description="The updated workflow state, with the re-evaluated chunk included"
    )
    agents_run: List[str] = Field(
        description="List of agents that were successfully run on the chunk"
    )
    processing_time_ms: Optional[float] = Field(
        description="Time taken to process the chunk in milliseconds", default=None
    )
