import logging

from langgraph.runtime import Runtime

from lib.agents.reference_text_extractor_v2 import ReferenceExtractorV2Agent
from lib.services.chunk_line_matcher import find_chunks_by_line_range
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionState,
)

logger = logging.getLogger(__name__)


@register_node(
    "Extract references",
    "Extract references using agentic tool calling",
)
async def extract_text_references_v2_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """Extract references from detected sections using LLM."""

    agent = ReferenceExtractorV2Agent(runtime.context)

    result = await agent.ainvoke({})

    # Get chunks for line-based matching
    chunks = await runtime.context.file_artifacts_service.get_chunks()

    # Create ExtractedReference objects with line numbers and chunk indices
    extracted_references = []
    for ref in result.references:
        # Find matching chunks by line overlap
        chunk_indices = []
        if chunks:
            chunk_indices = find_chunks_by_line_range(
                chunks, ref.start_line, ref.end_line
            )
            if not chunk_indices:
                logger.warning(
                    f'No chunk indices found for reference: "{ref.text}", start line: {ref.start_line}, end line: {ref.end_line}'
                )

        extracted_references.append(
            ExtractedReference(
                text=ref.text,
                start_line=ref.start_line,
                end_line=ref.end_line,
                chunk_indices=chunk_indices,
            )
        )

    logger.info(f"Extracted {len(extracted_references)} unique references")
    return {"extracted_references": extracted_references, "reasoning": result.reasoning}
