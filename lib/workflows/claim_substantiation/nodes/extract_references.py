import logging

from langgraph.runtime import Runtime

from lib.agents.formatting_utils import (
    format_supporting_documents_prompt_section_multiple,
)
from lib.agents.reference_extractor import ReferenceExtractorAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


@handle_workflow_node_errors()
async def extract_references(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"extract_references ({state.config.session_id}): starting")

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "references" not in agents_to_run:
        logger.info(
            f"extract_references ({state.config.session_id}): Skipping reference extraction (not in agents_to_run)"
        )
        return {}

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

    logger.info(f"extract_references ({state.config.session_id}): done")

    return {"references": res.references}
