from typing import List, Optional

from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.agents.models import ClaimCategory
from lib.workflows.claim_substantiation.state import (
    AnalyzedChunk,
    ClaimSubstantiatorState,
)
from lib.workflows.models import DocumentIssue, SeverityEnum


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

    return issues


def _find_claim_category(
    chunk: AnalyzedChunk, claim_index: int
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
