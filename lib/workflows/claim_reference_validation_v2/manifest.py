from typing import List, Type

from langgraph.graph import StateGraph

from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.services.chunk_line_matcher import (
    find_chunks_by_fuzzy_match,
    find_chunks_by_line_range,
)
from lib.workflows.chunk_utils import build_analyzed_chunks
from lib.workflows.claim_reference_validation_v2.graph import (
    build_claim_reference_validation_v2_graph,
)
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2Config,
    ClaimReferenceValidationV2ItemSource,
    ClaimReferenceValidationV2State,
)
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.types import WorkflowState


class ClaimReferenceValidationV2Manifest(
    WorkflowManifest[ClaimReferenceValidationV2State, ClaimReferenceValidationV2Config]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    name = "Claim Reference Validation v2"
    description = "Validate claims against references (v2)"
    order = 2
    required_dependencies = [
        WorkflowRunType.DOCUMENT_PROCESSING,
    ]
    is_experimental = True

    def get_state_type(self) -> Type[ClaimReferenceValidationV2State]:
        return ClaimReferenceValidationV2State

    def get_config_type(self) -> Type[ClaimReferenceValidationV2Config]:
        return ClaimReferenceValidationV2Config

    def build_graph(self) -> StateGraph:
        return build_claim_reference_validation_v2_graph()

    async def create_initial_state(
        self,
        config: ClaimReferenceValidationV2Config,
        existing_states: List[WorkflowState],
    ) -> ClaimReferenceValidationV2State:
        return ClaimReferenceValidationV2State(
            type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            config=config,
        )

    def convert_state_to_issues(
        self,
        state: ClaimReferenceValidationV2State,
        other_states: List[WorkflowState],
    ) -> List[DocumentIssue]:
        issues: List[DocumentIssue] = []

        if not state.response:
            return issues

        chunks = build_analyzed_chunks(other_states)

        for result in state.response.results:
            # if result.evidence_alignment == EvidenceAlignmentLevel.SUPPORTED:
            #     continue

            chunk_indices = find_chunks_by_fuzzy_match(
                chunks, result.key_sentence, result.line_start
            )
            chunk_index = chunk_indices[0] if chunk_indices else None
            severity = (
                SeverityEnum.HIGH
                if result.evidence_alignment
                in [
                    EvidenceAlignmentLevel.UNSUPPORTED,
                    EvidenceAlignmentLevel.UNVERIFIABLE,
                ]
                else (
                    SeverityEnum.MEDIUM
                    if result.evidence_alignment
                    == EvidenceAlignmentLevel.PARTIALLY_SUPPORTED
                    else SeverityEnum.NONE
                )
            )

            sources_text = (
                "\n".join(
                    [
                        self._format_evidence_source(source)
                        for source in result.evidence_sources
                    ]
                )
                if result.evidence_sources
                else "*No sources found*"
            )

            issues.append(
                DocumentIssue(
                    title="Invalid Claim Reference",
                    type=self.type,
                    description=f"**Evidence Alignment:** {result.evidence_alignment}\n\n{result.rationale}\n\n{result.feedback}",
                    severity=severity,
                    chunk_index=chunk_index,
                    chunk_indices=chunk_indices,
                    long_description=f"## Key Sentence\n\n> {result.key_sentence}\n\n## Rationale\n\n{result.long_rationale}\n\n## Checked sources\n\n{sources_text}",
                )
            )

        return issues

    def _format_evidence_source(
        self,
        source: ClaimReferenceValidationV2ItemSource,
    ) -> str:
        """Format an evidence source with a download link if file ID is available."""

        return f"- {source.supporting_document} - {source.location}\n\n\t> *{source.quote}*"
