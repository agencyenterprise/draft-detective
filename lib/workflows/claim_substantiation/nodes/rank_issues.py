from typing import List, Optional, Set

from lib.agents.citation_suggester import RecommendedAction
from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.agents.evidence_weighter import EvidenceWeighterRecommendedAction
from lib.agents.models import ClaimCategory
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
    DocumentIssue,
    SeverityEnum,
)


def rank_issues(state: ClaimSubstantiatorState) -> ClaimSubstantiatorState:
    """Rank issues based on analysis results from various workflow stages."""
    issues: List[DocumentIssue] = []

    # 1. Extract References: References without matching supporting documents
    for reference in state.references:
        if not reference.has_associated_supporting_document:
            issue = DocumentIssue(
                title="Missing supporting document for reference",
                description=f'Reference does not have an associated supporting document: "{reference.text}"',
                severity=SeverityEnum.LOW,
                chunk_index=_find_chunk_index_by_text(state, reference.text),
            )
            issues.append(issue)

    # 2. Reference Validation: Invalid references
    for validation in state.references_validated:
        if not validation.valid_reference:
            issue = DocumentIssue(
                title="Invalid reference",
                description=f'Possible invalid reference: "{validation.original_reference.text}"',
                severity=SeverityEnum.HIGH,
                chunk_index=_find_chunk_index_by_text(
                    state, validation.original_reference.text
                ),
            )
            issues.append(issue)

    # 3. Claim Categorization: Claims needing external verification without citations
    for chunk in state.chunks:
        if not chunk.claim_categories:
            continue

        # Check if chunk has citations
        has_citations = (
            chunk.citations
            and chunk.citations.citations
            and len(chunk.citations.citations) > 0
        )

        for category in chunk.claim_categories:
            claim_verification = next(
                (
                    s
                    for s in chunk.substantiations
                    if s.claim_index == category.claim_index
                ),
                None,
            )

            if (
                category.needs_external_verification
                and not has_citations
                and (
                    claim_verification is None
                    or claim_verification.evidence_alignment
                    != EvidenceAlignmentLevel.SUPPORTED
                )
            ):
                issue = DocumentIssue(
                    title="Unsupported claim",
                    description=f"Claim '{category.claim}' requires external verification but no citations were found.",
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=category.chunk_index,
                    claim_index=category.claim_index,
                    claim_category=category.claim_category,
                )
                issues.append(issue)

    # 4. Claim Verification: Unsupported and partially supported claims
    for chunk in state.chunks:
        if not chunk.substantiations:
            continue

        for substantiation in chunk.substantiations:
            if substantiation.evidence_alignment == EvidenceAlignmentLevel.UNSUPPORTED:
                issue = DocumentIssue(
                    title="Unsupported Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.HIGH,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=_find_claim_category(
                        chunk, substantiation.claim_index
                    ),
                )
                issues.append(issue)
            elif (
                substantiation.evidence_alignment
                == EvidenceAlignmentLevel.PARTIALLY_SUPPORTED
            ):
                issue = DocumentIssue(
                    title="Partially Supported Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=_find_claim_category(
                        chunk, substantiation.claim_index
                    ),
                )
                issues.append(issue)
            elif (
                substantiation.evidence_alignment == EvidenceAlignmentLevel.UNVERIFIABLE
            ):
                issue = DocumentIssue(
                    title="Unverifiable Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=_find_claim_category(
                        chunk, substantiation.claim_index
                    ),
                )
                issues.append(issue)

    # 5. Live Reports Analysis: Add citation and update claim actions
    for live_report in state.live_reports_analysis:
        chunk = _find_chunk_by_index(state, live_report.chunk_index)
        if chunk is None:
            continue

        if (
            live_report.claim_update_action
            == EvidenceWeighterRecommendedAction.ADD_CITATION
        ):
            issue = DocumentIssue(
                title="Additional Citation Recommended",
                description=live_report.rationale,
                severity=SeverityEnum.MEDIUM,
                chunk_index=live_report.chunk_index,
                claim_index=live_report.claim_index,
                claim_category=_find_claim_category(chunk, live_report.claim_index),
            )
            issues.append(issue)
        elif (
            live_report.claim_update_action
            == EvidenceWeighterRecommendedAction.UPDATE_CLAIM
        ):
            issue = DocumentIssue(
                title="Claim Update Recommended",
                description=live_report.rationale,
                severity=SeverityEnum.MEDIUM,
                chunk_index=live_report.chunk_index,
                claim_index=live_report.claim_index,
                claim_category=_find_claim_category(chunk, live_report.claim_index),
            )
            issues.append(issue)

    # 6. Inference Validation: Invalid inferences
    for chunk in state.chunks:
        if not chunk.inference_validations:
            continue

        for validation in chunk.inference_validations:
            if not validation.valid:
                issue = DocumentIssue(
                    title="Invalid Inference",
                    description=validation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=validation.chunk_index,
                    claim_index=validation.claim_index,
                    claim_category=_find_claim_category(chunk, validation.claim_index),
                )
                issues.append(issue)

    # 7. Citation Suggestions: Actionable citation recommendations
    issues.extend(_build_citation_suggestion_issues(state))

    issues.sort(key=lambda x: x.severity.sort_index(), reverse=True)

    return {"ranked_issues": issues}


def _find_claim_category(
    chunk: DocumentChunk, claim_index: int
) -> Optional[ClaimCategory]:
    for category in chunk.claim_categories:
        if category.claim_index == claim_index:
            return category.claim_category

    return None


def _find_chunk_by_index(
    state: ClaimSubstantiatorState, chunk_index: int
) -> Optional[DocumentChunk]:
    for chunk in state.chunks:
        if chunk.chunk_index == chunk_index:
            return chunk

    return None


def _find_chunk_index_by_text(state: ClaimSubstantiatorState, text: str) -> int:
    for chunk in state.chunks:
        if text in chunk.content:
            return chunk.chunk_index

    return None


# Actionable citation actions that warrant an issue
ACTIONABLE_CITATION_ACTIONS: Set[RecommendedAction] = {
    RecommendedAction.ADD_NEW_CITATION,
    RecommendedAction.REPLACE_EXISTING_REFERENCE,
    RecommendedAction.CITE_EXISTING_REFERENCE_IN_NEW_PLACE,
}


def _build_citation_suggestion_issues(
    state: ClaimSubstantiatorState,
) -> List[DocumentIssue]:
    """Build issues for actionable citation suggestions."""
    issues = []

    for chunk in state.chunks:
        for suggestion in chunk.citation_suggestions:
            actionable_refs = [
                ref
                for ref in (suggestion.relevant_references or [])
                if ref.recommended_action in ACTIONABLE_CITATION_ACTIONS
            ]
            if actionable_refs:
                ref_summary = "\n".join(
                    f"  • {ref.title} ({ref.recommended_action.value})"
                    for ref in actionable_refs[:3]
                )
                issues.append(
                    DocumentIssue(
                        title="Citation Suggestion",
                        description=(
                            f"{suggestion.rationale}\n\n"
                            f"Consider these references:\n{ref_summary}"
                        ),
                        severity=SeverityEnum.LOW,
                        chunk_index=chunk.chunk_index,
                    )
                )

    return issues
