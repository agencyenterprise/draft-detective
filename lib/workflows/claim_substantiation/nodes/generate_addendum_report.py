# %%
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple

from lib.agents.addendum_report_generator import addendum_report_generator_agent
from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.decorators import handle_workflow_node_errors


logger = logging.getLogger(__name__)


def _build_claim_category_index(
    state: ClaimSubstantiatorState,
) -> Dict[Tuple[int, int], Any]:
    """Map (chunk_index, claim_index) -> claim_category."""
    index: Dict[Tuple[int, int], Any] = {}
    for chunk in state.chunks or []:
        for cat in chunk.claim_categories or []:
            index[(cat.chunk_index, cat.claim_index)] = cat.claim_category
    return index


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
    state: ClaimSubstantiatorState,
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
    category_index = _build_claim_category_index(state)

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
                "claim_category": category_index.get((lr.chunk_index, lr.claim_index)),
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

    addendum_report = await addendum_report_generator_agent.ainvoke(prompt_kwargs)

    return {"addendum_report": addendum_report}


if __name__ == "__main__":
    import asyncio
    import argparse
    from lib.services.file import FileDocument
    from lib.agents.claim_extractor import Claim, ClaimResponse
    from lib.agents.claim_categorizer import (
        ClaimCategorizationResponseWithClaimIndex,
        ClaimCategory,
    )
    from lib.agents.evidence_weighter import (
        EvidenceWeighterResponseWithClaimIndex,
        EvidenceWeighterRecommendedAction,
        ReferenceAlignmentLevel,
    )
    from lib.agents.literature_review import QualityLevel
    from lib.agents.addendum_generator import (
        Addendum,
        AddendumItem,
        AddendumSections,
        AddendumSeverity,
    )
    from lib.workflows.claim_substantiation.state import (
        DocumentChunk,
        SubstantiationWorkflowConfig,
    )
    import nest_asyncio

    nest_asyncio.apply()

    parser = argparse.ArgumentParser(description="Test generate_addendum node")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args, _ = parser.parse_known_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    async def _main():
        file = FileDocument(
            file_name="test.md",
            file_path="/tmp/test.md",
            file_type="text/markdown",
            markdown="# Title\n\nTest paragraph with a claim.",
        )

        claim_text = "X causes Y"
        chunk = DocumentChunk(
            content="X causes Y.",
            chunk_index=0,
            paragraph_index=0,
            claims=ClaimResponse(
                claims=[
                    Claim(
                        text="X causes Y.",
                        claim=claim_text,
                        rationale="test rationale",
                    ),
                ],
                rationale="rationale",
            ),
            claim_categories=[
                ClaimCategorizationResponseWithClaimIndex(
                    chunk_index=0,
                    claim_index=0,
                    claim=claim_text,
                    claim_category=ClaimCategory.ESTABLISHED,
                    rationale="cat rationale",
                    needs_external_verification=True,
                )
            ],
            live_reports_analysis=[
                EvidenceWeighterResponseWithClaimIndex(
                    chunk_index=0,
                    claim_index=0,
                    newer_references=[],
                    newer_references_alignment=ReferenceAlignmentLevel.UNSUPPORTED,
                    claim_update_action=EvidenceWeighterRecommendedAction.UPDATE_CLAIM,
                    rationale="evidence rationale",
                    confidence_level=QualityLevel.HIGH,
                    rewritten_claim="X does not consistently cause Y",
                )
            ],
        )

        state = ClaimSubstantiatorState(
            file=file,
            config=SubstantiationWorkflowConfig(run_live_reports=True),
            chunks=[chunk],
        )

        # Stub the agent to avoid network calls
        from lib.agents import addendum_report_generator as ag

        async def _fake_ainvoke(prompt_kwargs, config=None):
            item = AddendumItem(
                chunk_index=0,
                claim_index=0,
                original_claim=claim_text,
                rewritten_claim="X does not consistently cause Y",
                claim_category=ClaimCategory.ESTABLISHED,
                evidence_alignment=ReferenceAlignmentLevel.UNSUPPORTED,
                recommended_action=EvidenceWeighterRecommendedAction.UPDATE_CLAIM,
                action_summary="Revise claim to qualify causality and add updated citations.",
                confidence=QualityLevel.HIGH,
                rationale="High-impact contradiction to thesis.",
                severity=AddendumSeverity.HIGH,
            )
            return Addendum(
                summary="Recent evidence undermines a foundational claim.",
                sections=AddendumSections(background=[item]),
            )

        ag.addendum_report_generator_agent.ainvoke = _fake_ainvoke

        delta = await generate_addendum_report(state)
        addendum_report = delta.get("addendum_report")
        print(addendum_report)

    asyncio.run(_main())
