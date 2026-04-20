import logging
import uuid

from langgraph.runtime import Runtime

from lib.agents.reference_text_extractor_v2 import ReferenceExtractorV2Agent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionState,
)

logger = logging.getLogger(__name__)


@register_node("Extract references")
async def extract_text_references_v2_node(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> dict:
    """Extract references from document using agentic tool calling."""

    agent = ReferenceExtractorV2Agent(runtime.context)

    result, messages = await agent.ainvoke({})

    extracted_references = [
        ExtractedReference(
            id=str(uuid.uuid4()),
            text=ref.text,
            start_line=ref.start_line,
            end_line=ref.end_line,
        )
        for ref in result.references
    ]

    logger.info(f"Extracted {len(extracted_references)} unique references")
    return {
        "extracted_references": extracted_references,
        "reasoning": result.reasoning,
        "messages": messages,
    }
