import logging

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import (
    format_supporting_documents_prompt_section_multiple,
)
from lib.agents.reference_extractor import ReferenceExtractorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.reference_extraction.state import ReferenceExtractionState
from lib.workflows.decorators import register_node

logger = logging.getLogger(__name__)


@register_node(
    "Extract references",
    "Extract references from the document",
)
async def extract_references(
    state: ReferenceExtractionState, runtime: Runtime[ContextSchema]
) -> ReferenceExtractionState:
    markdown = state.file.markdown

    supporting_documents = format_supporting_documents_prompt_section_multiple(
        state.supporting_files, truncate_at_character_count=1000
    )

    reference_extractor_agent = ReferenceExtractorAgent(runtime.context)

    res = await reference_extractor_agent.ainvoke(
        {
            "full_document": markdown,
            "supporting_documents": supporting_documents,
        }
    )

    return {"references": res.references}
