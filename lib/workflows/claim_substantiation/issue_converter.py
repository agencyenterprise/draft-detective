from typing import List, Optional

from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.agents.models import ClaimCategory
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    DocumentChunk,
    DocumentIssue,
    SeverityEnum,
)


def convert_state_to_issues(
    state: ClaimSubstantiatorState, claim_state: ClaimSubstantiatorState
) -> List[DocumentIssue]:
    """Convert ClaimSubstantiatorState to issues."""
    issues: List[DocumentIssue] = []

    # Ensure we have chunks
    if not state.chunks:
        return issues

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

    # 2. Claim Categorization: Claims needing external verification without citations
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

    # 3. Claim Verification: Unsupported and partially supported claims
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

    # 4. Inference Validation: Invalid inferences
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

    return issues


def _find_claim_category(
    chunk: DocumentChunk, claim_index: int
) -> Optional[ClaimCategory]:
    """Find claim category for a given claim index in a chunk."""
    for category in chunk.claim_categories:
        if category.claim_index == claim_index:
            return category.claim_category

    return None


def _find_chunk_index_by_text(
    state: ClaimSubstantiatorState, text: str
) -> Optional[int]:
    """Find chunk index by searching for text in chunk content."""
    for chunk in state.chunks:
        if text in chunk.content:
            return chunk.chunk_index

    return None
