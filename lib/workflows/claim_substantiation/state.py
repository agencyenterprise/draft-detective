from typing import Annotated, Dict, List, Literal, Optional

from pydantic import Field

from lib.agents.citation_detector import CitationResponseWithChunkIndex
from lib.agents.claim_categorizer import ClaimCategorizationResponseWithClaimIndex
from lib.agents.claim_extractor import ClaimResponse, ClaimResponseWithChunkIndex
from lib.agents.document_summarizer import DocumentSummary
from lib.agents.models import ChunkWithIndex
from lib.models.bibliography_item import BibliographyItem
from lib.agents.toulmin_claim_extractor import ToulminClaimResponse
from lib.services.docling_models import ChunkToItems
from lib.services.file import FileDocument
from lib.workflows.models import BaseWorkflowConfig, BaseWorkflowState, WorkflowRunType


class SubstantiationWorkflowConfig(BaseWorkflowConfig):
    """Configuration model for claim substantiation workflow"""

    type: Literal[WorkflowRunType.CLAIM_SUBSTANTIATION] = Field(
        WorkflowRunType.CLAIM_SUBSTANTIATION
    )
    target_chunk_indices: Optional[List[int]] = Field(
        default=None,
        description="Specific chunk indices to process (None = process all chunks)",
    )
    agents_to_run: Optional[List[str]] = Field(
        default=None, description="Specific agents to run (None = run all agents)"
    )
    workflow_types: Optional[List[WorkflowRunType]] = Field(
        default=None, description="List of workflow types to run"
    )


class AnalyzedChunk(ChunkWithIndex):
    """Enriched document chunk with all claim analysis results.

    Extends the base ChunkWithIndex with claim extraction, citation detection,
    categorization, substantiation, and inference validation results.
    """

    claims: Optional[ClaimResponseWithChunkIndex] = None
    citations: Optional[CitationResponseWithChunkIndex] = None
    claim_categories: List[ClaimCategorizationResponseWithClaimIndex] = []


def conciliate_chunks(
    a: List[AnalyzedChunk], b: List[AnalyzedChunk]
) -> List[AnalyzedChunk]:
    """
    Conciliate two lists of AnalyzedChunk by merging their properties.

    This reducer function is used by LangGraph to handle multiple updates to the same
    chunks field from different nodes running in parallel.

    Args:
        a: First list of AnalyzedChunk (existing state)
        b: Second list of AnalyzedChunk (new updates)

    Returns:
        Merged list of AnalyzedChunk with combined properties
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

            chunks_by_index[updated_chunk.chunk_index] = AnalyzedChunk(**merged_data)

    # Return chunks in order by chunk_index
    return [chunks_by_index[i] for i in sorted(chunks_by_index.keys())]


class ClaimSubstantiatorState(BaseWorkflowState):
    type: Literal[WorkflowRunType.CLAIM_SUBSTANTIATION] = Field(
        WorkflowRunType.CLAIM_SUBSTANTIATION
    )

    # Inputs
    file: FileDocument
    supporting_files: Optional[List[FileDocument]] = None
    config: SubstantiationWorkflowConfig

    # Outputs
    references: List[BibliographyItem] = []
    chunks: Annotated[List[AnalyzedChunk], conciliate_chunks] = []
    main_document_summary: Optional[DocumentSummary] = Field(
        default=None, description="The summary of the main document"
    )
    supporting_documents_summaries: Optional[Dict[int, DocumentSummary]] = Field(
        default=None,
        description="Dictionary mapping supporting file indices to their summaries",
    )
    chunk_to_items: Optional[ChunkToItems] = Field(
        default=None,
        description="Mapping from chunk indices to Docling items/regions for rendering",
    )

    def get_paragraph_chunks(self, paragraph_index: int) -> List[AnalyzedChunk]:
        return [
            chunk for chunk in self.chunks if chunk.paragraph_index == paragraph_index
        ]

    def get_paragraph(self, paragraph_index: int) -> str:
        paragraph_chunks = self.get_paragraph_chunks(paragraph_index)
        return "\n".join([chunk.content for chunk in paragraph_chunks])
