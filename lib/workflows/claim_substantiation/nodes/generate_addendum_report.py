from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langgraph.runtime import Runtime

from lib.agents.addendum_report_generator import AddendumReportGeneratorAgent
from lib.workflows.claim_substantiation.context import ContextSchema
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors

logger = logging.getLogger(__name__)


def _get_original_claim_text(chunk: Any, claim_index: int) -> str:
    if chunk.claims and getattr(chunk.claims, "claims", None):
        claims_list = chunk.claims.claims
        if 0 <= claim_index < len(claims_list):
            claim_obj = claims_list[claim_index]
            # Prefer normalized field name "claim" if present, fallback to text
            return getattr(claim_obj, "claim", None) or getattr(claim_obj, "text", "")
    return ""


@handle_workflow_node_errors()
async def generate_addendum_report(
    state: ClaimSubstantiatorState, runtime: Runtime[ContextSchema]
) -> ClaimSubstantiatorState:
    logger.info(f"generate_addendum_report ({state.config.session_id}): starting")

    if not state.config.run_live_reports:
        logger.info(
            f"generate_addendum_report ({state.config.session_id}): skipping (run_live_reports is False)"
        )
        return {}

    agents_to_run = state.config.agents_to_run
    if agents_to_run and "live_reports" not in agents_to_run:
        logger.info(
            f"generate_addendum_report ({state.config.session_id}): Skipping (live_reports not in agents_to_run)"
        )
        return {}

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
        logger.info(
            f"generate_addendum_report ({state.config.session_id}): no live report records, skipping"
        )
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
