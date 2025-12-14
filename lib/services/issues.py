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
from lib.workflows.citation_suggester.state import CitationSuggesterState
from lib.workflows.literature_review.state import LiteratureReviewState
from lib.workflows.live_reports.state import LiveReportsState
from lib.workflows.methodological_alignment.state import MethodologicalAlignmentState
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_downloader.state import ReferenceDownloaderState
from lib.workflows.reference_validation.state import ReferenceValidationState
from lib.workflows.registry import WorkflowState


def convert_to_issues(results: List[WorkflowState]) -> List[DocumentIssue]:
    """Convert workflow results to issues, dispatching to appropriate converter for each state type."""
    all_issues: List[DocumentIssue] = []

    # Find ClaimSubstantiatorState to pass to reference validation converter
    claim_state: Optional[ClaimSubstantiatorState] = None
    for result in results:
        if result.type == WorkflowRunType.CLAIM_SUBSTANTIATION:
            claim_state = result
            break

    for result in results:
        issues = _convert_state_to_issues(result, claim_state)
        all_issues.extend(issues)

    # Sort all issues by severity
    all_issues.sort(key=lambda x: x.severity.sort_index(), reverse=True)

    return all_issues


def _convert_state_to_issues(
    state: WorkflowState,
    claim_state: Optional[ClaimSubstantiatorState] = None,
) -> List[DocumentIssue]:
    """Dispatch to the appropriate converter based on state type."""
    match state.type:
        case WorkflowRunType.CLAIM_SUBSTANTIATION:
            return convert_claim_substantiator_state_issues(state)
        case WorkflowRunType.METHODOLOGICAL_ALIGNMENT:
            return convert_methodological_alignment_state_issues(state)
        case WorkflowRunType.REFERENCE_DOWNLOADER:
            return convert_reference_downloader_state_issues(state)
        case WorkflowRunType.LITERATURE_REVIEW:
            return convert_literature_review_state_issues(state)
        case WorkflowRunType.LIVE_REPORTS:
            return convert_live_reports_state_issues(state)
        case WorkflowRunType.REFERENCE_VALIDATION:
            return convert_reference_validation_state_issues(state, claim_state)
        case WorkflowRunType.CITATION_SUGGESTER:
            return convert_citation_suggester_state_issues(state)
        case _:
            return []


def convert_claim_substantiator_state_issues(
    state: ClaimSubstantiatorState,
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


def convert_methodological_alignment_state_issues(
    state: MethodologicalAlignmentState,
) -> List[DocumentIssue]:
    """Convert MethodologicalAlignmentState to issues."""
    return []


def convert_reference_downloader_state_issues(
    state: ReferenceDownloaderState,
) -> List[DocumentIssue]:
    """Convert ReferenceDownloaderState to issues."""
    return []


def convert_literature_review_state_issues(
    state: LiteratureReviewState,
) -> List[DocumentIssue]:
    """Convert LiteratureReviewState to issues."""
    return []


def convert_live_reports_state_issues(state: LiveReportsState) -> List[DocumentIssue]:
    """Convert LiveReportsState to issues."""

    issues: List[DocumentIssue] = []

    for live_report in state.live_reports_analysis:
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
            )
            issues.append(issue)

    return issues


def convert_reference_validation_state_issues(
    state: ReferenceValidationState,
    claim_state: Optional[ClaimSubstantiatorState] = None,
) -> List[DocumentIssue]:
    """Convert ReferenceValidationState to issues."""
    issues: List[DocumentIssue] = []

    # Reference Validation: Invalid references
    for validation in state.reference_validations:
        if not validation.valid_reference:
            # Try to find chunk_index from claim_state if available
            chunk_index: Optional[int] = None
            if claim_state:
                chunk_index = _find_chunk_index_by_text(
                    claim_state, validation.original_reference.text
                )

            issue = DocumentIssue(
                title="Invalid reference",
                description=f'Possible invalid reference: "{validation.original_reference.text}"',
                severity=SeverityEnum.HIGH,
                chunk_index=chunk_index,
            )
            issues.append(issue)

    return issues


def convert_citation_suggester_state_issues(
    state: CitationSuggesterState,
) -> List[DocumentIssue]:
    """Convert CitationSuggesterState to issues."""

    issues = []

    for suggestion in state.citation_suggestions:
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
                    chunk_index=suggestion.chunk_index,
                    claim_index=suggestion.claim_index,
                )
            )

    return issues


def _find_claim_category(
    chunk: DocumentChunk, claim_index: int
) -> Optional[ClaimCategory]:
    for category in chunk.claim_categories:
        if category.claim_index == claim_index:
            return category.claim_category

    return None


def _find_chunk_index_by_text(
    state: ClaimSubstantiatorState, text: str
) -> Optional[int]:
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
