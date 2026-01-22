import json
import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.addendum_report_generator import AddendumReportGeneratorAgent
from lib.agents.formatting_utils import format_domain_context, format_audience_context
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
):
    file_artifacts_service = runtime.context.file_artifacts_service

    # Fetch artifacts from file artifacts service
    chunks = await file_artifacts_service.get_chunks()
    document_summary = await file_artifacts_service.get_file_summary(state.file_id)

    # Create a lookup dictionary for chunks by chunk_index
    chunks_by_index = {chunk.chunk_index: chunk for chunk in chunks}

    # Collect live reports results across all chunks
    records: List[Dict[str, Any]] = []

    for live_report in state.live_reports_analysis or []:
        chunk = chunks_by_index.get(live_report.chunk_index)

        if chunk is None:
            logger.debug(
                "Skipping addendum report for chunk %s: chunk not found",
                live_report.chunk_index,
            )
            continue

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
        "domain_context": format_domain_context(state.config.domain),
        "audience_context": format_audience_context(state.config.target_audience),
        "document_title": document_summary.title if document_summary else "",
        "document_summary": document_summary.summary if document_summary else "",
        "records_json": json.dumps(records, default=str),
    }

    addendum_report_generator_agent = AddendumReportGeneratorAgent(runtime.context)
    addendum_report = await addendum_report_generator_agent.ainvoke(prompt_kwargs)

    return {"addendum_report": addendum_report}
