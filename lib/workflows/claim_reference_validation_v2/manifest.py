"""Manifest for Claim Reference Validation V2 workflow."""

from typing import List, Optional, Type, cast

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph, RunnableConfig

from lib.agents.citation_validator import CitationIssueItem
from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.services.chunk_line_matcher import find_chunks_by_line_range
from lib.services.file import FileDocument
from lib.workflows.chunk_utils import build_analyzed_chunks
from lib.workflows.claim_reference_validation_v2.graph import (
    build_claim_reference_validation_v2_graph,
)
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2Config,
    ClaimReferenceValidationV2State,
    SectionVerificationStatus,
)
from lib.workflows.document_processing.state import DocumentProcessingState
from lib.workflows.manifest import WorkflowManifest
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType
from lib.workflows.util import get_state_by_type
from lib.workflows.workflow_types import WorkflowState

_ISSUE_CONFIG = {
    EvidenceAlignmentLevel.UNSUPPORTED: ("Unsupported Citation", SeverityEnum.HIGH),
    EvidenceAlignmentLevel.PARTIALLY_SUPPORTED: (
        "Partially Supported Citation",
        SeverityEnum.MEDIUM,
    ),
    EvidenceAlignmentLevel.UNVERIFIABLE: ("Unverifiable Citation", SeverityEnum.MEDIUM),
    EvidenceAlignmentLevel.SUPPORTED: ("Supported Citation", SeverityEnum.NONE),
}


def _get_file_by_id(
    supporting_files: Optional[List[FileDocument]], file_id: str
) -> Optional[FileDocument]:
    if not supporting_files:
        return None
    return next((f for f in supporting_files if f.file_id == file_id), None)


def _format_evidence_source(
    source,
    supporting_files: Optional[List[FileDocument]],
) -> str:
    file = _get_file_by_id(supporting_files, source.file_id)
    label = file.file_name if file else "View file"
    file_link = f"[{label}](/api/files/download/{source.file_id})"

    if not source.quote and not source.location:
        return f"- {file_link}"
    if not source.quote:
        return f"- {file_link} - {source.location}"
    if not source.location:
        return f"- {file_link}\n\n\t> *{source.quote}*"
    return f"- {file_link} - {source.location}\n\n\t> *{source.quote}*"


def _build_issue(
    item: CitationIssueItem,
    chunks,
    supporting_files: Optional[List[FileDocument]],
    workflow_type: WorkflowRunType,
) -> Optional[DocumentIssue]:
    if item.evidence_alignment not in _ISSUE_CONFIG:
        return None

    title, severity = _ISSUE_CONFIG[item.evidence_alignment]

    chunk_indices = (
        find_chunks_by_line_range(chunks, item.line_start, item.line_end)
        if chunks
        else None
    )

    sources_text = (
        "\n".join(
            _format_evidence_source(source, supporting_files)
            for source in item.evidence_sources
        )
        if item.evidence_sources
        else "*No sources found*"
    )

    long_description = (
        f"**Cited text:**\n\n> {item.quoted_text}\n\n"
        f"**Evidence Alignment:** {item.evidence_alignment}\n\n"
        f"**Feedback to resolve:** {item.feedback}\n\n"
        f"### Checked sources\n\n{sources_text}\n\n"
        f"### Citation-to-file mapping\n\n"
        f"{item.citation_to_file_mapping or 'No citation-to-file mapping provided'}"
    )

    return DocumentIssue(
        title=title,
        description=item.rationale,
        severity=severity,
        type=workflow_type,
        chunk_indices=chunk_indices or None,
        long_description=long_description,
    )


class ClaimReferenceValidationV2Manifest(
    WorkflowManifest[ClaimReferenceValidationV2State, ClaimReferenceValidationV2Config]
):
    type = WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2
    name = "Claim Reference Validation"
    description = (
        "Checks every citation in your document against its referenced source and "
        "flags claims that aren't supported, are only partially supported, or can't "
        "be verified."
    )
    needs_web_search = False
    is_experimental = True
    required_dependencies = [
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_FILE_MATCHING,
        WorkflowRunType.HUMAN_APPROVAL,
    ]
    optional_dependencies = [
        WorkflowRunType.CHUNK_SPLITTING,
    ]

    def get_state_type(self) -> Type[ClaimReferenceValidationV2State]:
        return ClaimReferenceValidationV2State

    def get_config_type(self) -> Type[ClaimReferenceValidationV2Config]:
        return ClaimReferenceValidationV2Config

    def build_graph(self) -> StateGraph:
        return build_claim_reference_validation_v2_graph()

    async def on_cancel(
        self,
        state: ClaimReferenceValidationV2State,
        app: CompiledStateGraph,
        config: RunnableConfig,
    ) -> None:
        updated = [
            (
                item.model_copy(update={"status": SectionVerificationStatus.CANCELLED})
                if item.status == SectionVerificationStatus.PENDING
                else item
            )
            for item in state.section_verifications
        ]
        await app.aupdate_state(
            config,
            {"section_verifications": updated},
            as_node="finalize_results",
        )

    async def create_initial_state(
        self,
        config: ClaimReferenceValidationV2Config,
        existing_states: List[WorkflowState],
        revision: int,
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
        doc_processing_state = get_state_by_type(
            WorkflowRunType.DOCUMENT_PROCESSING, other_states
        )
        supporting_files = (
            cast(DocumentProcessingState, doc_processing_state).supporting_files
            if doc_processing_state
            else None
        )

        chunks = build_analyzed_chunks(other_states)

        issues = []
        for item in state.citation_issues:
            issue = _build_issue(item, chunks, supporting_files, self.type)
            if issue:
                issues.append(issue)

        return issues
