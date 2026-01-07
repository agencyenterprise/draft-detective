import json
import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.addendum_report_generator import AddendumReportGeneratorAgent
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.live_reports.state import LiveReportsState

logger = logging.getLogger(__name__)


@register_node(
    "Live Reports: generate addendum",
    "Generate an addendum report from the live reports analysis",
)
async def generate_addendum_report(
    state: LiveReportsState, runtime: Runtime[ContextSchema]
) -> LiveReportsState:
    # Collect live reports results across all chunks
    records: List[Dict[str, Any]] = []

    for live_report in state.live_reports_analysis or []:
        chunk = state.chunks[live_report.chunk_index]

        if chunk.claims is None or not chunk.claims.claims:
            logger.debug(
                "Skipping addendum report for chunk %s: claims not found",
                live_report.chunk_index,
            )
            continue

        claim = chunk.claims.claims[live_report.claim_index]

        record: Dict[str, Any] = {
            "chunk_index": live_report.chunk_index,
            "claim_index": live_report.claim_index,
            "original_claim": claim.claim,
            "rewritten_claim": live_report.rewritten_claim,
            "evidence_alignment": live_report.newer_references_alignment,
            "recommended_action": live_report.claim_update_action,
            "confidence": live_report.confidence_level,
            "rationale": live_report.rationale,
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
