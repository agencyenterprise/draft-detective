from typing import List, Type

from langgraph.graph import StateGraph

from lib.workflows.claim_reference_validation.graph import (
    build_claim_reference_validation_graph,
)
from lib.workflows.claim_reference_validation.state import (
    ClaimReferenceValidationState,
    ClaimReferenceValidationWorkflowConfig,
)
from lib.workflows.claim_substantiation.issue_converter import _find_claim_category
from lib.workflows.claim_substantiation.state import (
    ClaimSubstantiatorState,
    AnalyzedChunk,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.base import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState
from lib.workflows.util import get_state_by_type_or_raise


class ClaimReferenceValidationManifest(
    WorkflowManifest[
        ClaimReferenceValidationState, ClaimReferenceValidationWorkflowConfig
    ]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION
    name = "Claim Reference Validation"
    description = """Validate claims by checking them against supporting documents using RAG (Retrieval-Augmented Generation). Retrieves relevant passages from supporting documents and verifies whether claims are supported, partially supported, unsupported, or unverifiable."""
    needs_web_search = False
    required_dependencies = [WorkflowRunType.CLAIM_SUBSTANTIATION]

    def get_state_type(self) -> Type[ClaimReferenceValidationState]:
        """Get the type of the workflow state."""
        return ClaimReferenceValidationState

    def get_config_type(self) -> Type[ClaimReferenceValidationWorkflowConfig]:
        """Get the type of the workflow config."""
        return ClaimReferenceValidationWorkflowConfig

    def build_graph(self) -> StateGraph:
        """Build and return the graph of the workflow."""
        return build_claim_reference_validation_graph()

    async def create_initial_state(
        self,
        config: ClaimReferenceValidationWorkflowConfig,
        existing_states: List[WorkflowState],
    ) -> ClaimReferenceValidationState:
        """Create and return the initial state of the workflow."""

        claim_state: ClaimSubstantiatorState = get_state_by_type_or_raise(
            WorkflowRunType.CLAIM_SUBSTANTIATION, existing_states
        )

        # Carry over optional context from the claim workflow if not provided
        if config.domain is None:
            config.domain = claim_state.config.domain
        if config.target_audience is None:
            config.target_audience = claim_state.config.target_audience
        if config.publication_date is None:
            config.publication_date = claim_state.config.publication_date

        return ClaimReferenceValidationState(
            type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            config=config,
            file=claim_state.file,
            supporting_files=claim_state.supporting_files,
            chunks=claim_state.chunks,
            references=claim_state.references,
            main_document_summary=claim_state.main_document_summary,
        )

    def convert_state_to_issues(
        self,
        state: ClaimReferenceValidationState,
        claim_state: ClaimSubstantiatorState,
    ) -> List[DocumentIssue]:
        """Convert ClaimReferenceValidationState to issues."""
        from lib.agents.claim_verifier import EvidenceAlignmentLevel

        issues: List[DocumentIssue] = []

        # Claim Verification: Unsupported and partially supported claims
        for substantiation in state.substantiations:
            if substantiation.evidence_alignment == EvidenceAlignmentLevel.UNSUPPORTED:
                # Find the chunk to get claim category
                chunk: AnalyzedChunk | None = None
                for c in state.chunks:
                    if c.chunk_index == substantiation.chunk_index:
                        chunk = c
                        break

                issue = DocumentIssue(
                    title="Unsupported Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.HIGH,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=(
                        _find_claim_category(chunk, substantiation.claim_index)
                        if chunk
                        else None
                    ),
                )
                issues.append(issue)
            elif (
                substantiation.evidence_alignment
                == EvidenceAlignmentLevel.PARTIALLY_SUPPORTED
            ):
                # Find the chunk to get claim category
                chunk: AnalyzedChunk | None = None
                for c in state.chunks:
                    if c.chunk_index == substantiation.chunk_index:
                        chunk = c
                        break

                issue = DocumentIssue(
                    title="Partially Supported Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=(
                        _find_claim_category(chunk, substantiation.claim_index)
                        if chunk
                        else None
                    ),
                )
                issues.append(issue)
            elif (
                substantiation.evidence_alignment == EvidenceAlignmentLevel.UNVERIFIABLE
            ):
                # Find the chunk to get claim category
                chunk: AnalyzedChunk | None = None
                for c in state.chunks:
                    if c.chunk_index == substantiation.chunk_index:
                        chunk = c
                        break

                issue = DocumentIssue(
                    title="Unverifiable Claim",
                    description=substantiation.rationale,
                    severity=SeverityEnum.MEDIUM,
                    chunk_index=substantiation.chunk_index,
                    claim_index=substantiation.claim_index,
                    claim_category=(
                        _find_claim_category(chunk, substantiation.claim_index)
                        if chunk
                        else None
                    ),
                )
                issues.append(issue)

        # Claim Categorization: Claims needing external verification without citations
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
                        for s in state.substantiations
                        if chunk.chunk_index == s.chunk_index
                        and s.claim_index == category.claim_index
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

        return issues
