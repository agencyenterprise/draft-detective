import logging

from langchain_core.runnables.config import ensure_config
from langgraph.runtime import Runtime

from lib.agents.reference_text_extractor_v2 import ReferenceExtractorV2Agent
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

    # Create ExtractedReference objects with unique IDs
    extracted_references = [ExtractedReference(text=text) for text in result.references]

    logger.info(f"Extracted {len(extracted_references)} unique references")
    return {"extracted_references": extracted_references, "reasoning": result.reasoning}
