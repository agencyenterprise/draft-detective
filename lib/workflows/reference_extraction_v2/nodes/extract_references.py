"""Node for extracting references using the v2 agent."""

import logging

from langgraph.runtime import Runtime

from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.reference_extraction_v2.agents.reference_extractor import (
    ReferenceExtractorV2Agent,
)
from lib.workflows.reference_extraction_v2.state import ReferenceExtractionV2State

logger = logging.getLogger(__name__)


@register_node(
    "Extract references v2",
    "Extract bibliographic references using AI agent with document search",
)
async def extract_references_node(
    state: ReferenceExtractionV2State, runtime: Runtime[ContextSchema]
) -> dict:
    """Extract references from document using the v2 agent with search tool."""
    main_file = await runtime.context.file_artifacts_service.get_main_file()

    if not main_file or not main_file.markdown:
        logger.warning("No main document found or document has no content")
        return {"references": []}

    agent = ReferenceExtractorV2Agent(runtime.context)
    result = await agent.ainvoke({})

    logger.info(f"Extracted {len(result.references)} references")
    return {"reasoning": result.reasoning, "references": result.references}
