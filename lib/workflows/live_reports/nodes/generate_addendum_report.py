import json
import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.addendum_report_generator import AddendumReportGeneratorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.live_reports.state import LiveReportsState

logger = logging.getLogger(__name__)


def _get_original_claim_text(chunk: Any, claim_index: int) -> str:
    """Get the original claim text from the chunk."""
    if hasattr(chunk, "claims") and chunk.claims and hasattr(chunk.claims, "claims"):
        claims = chunk.claims.claims
        if 0 <= claim_index < len(claims):
            claim_obj = claims[claim_index]
            if hasattr(claim_obj, "claim"):
                return getattr(claim_obj, "claim")
            if hasattr(claim_obj, "text"):
                return getattr(claim_obj, "text")
    return ""


@register_node(
    "Live Reports: generate addendum",
    "Generate an addendum report from the live reports analysis",
)
async def generate_addendum_report(
    state: LiveReportsState, runtime: Runtime[ContextSchema]
) -> LiveReportsState:
    # Collect live reports results across all chunks
    records: List[Dict[str, Any]] = []

    for chunk in state.chunks or []:
        if not chunk.live_reports_analysis:
            continue
        for lr in chunk.live_reports_analysis:
            original_claim = _get_original_claim_text(chunk, lr.claim_index)
            record: Dict[str, Any] = {
                "chunk_index": lr.chunk_index,
                "claim_index": lr.claim_index,
                "original_claim": original_claim,
                "rewritten_claim": lr.rewritten_claim,
                "evidence_alignment": lr.newer_references_alignment,
                "recommended_action": lr.claim_update_action,
                "confidence": lr.confidence_level,
                "rationale": lr.rationale,
            }
            records.append(record)

    if not records:
        logger.info("generate_addendum_report: no live report records, skipping")
        return {}

    prompt_kwargs = {
        "domain_context": state.config.domain or "",
        "audience_context": state.config.target_audience or "",
        "document_title": (
            state.main_document_summary.title if state.main_document_summary else ""
        ),
        "document_summary": (
            state.main_document_summary.summary if state.main_document_summary else ""
        ),
        "records_json": json.dumps(records, default=str),
    }

    addendum_report_generator_agent = AddendumReportGeneratorAgent(runtime.context)
    addendum_report = await addendum_report_generator_agent.ainvoke(prompt_kwargs)

    return {"addendum_report": addendum_report}
