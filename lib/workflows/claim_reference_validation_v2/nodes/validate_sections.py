"""Graph nodes for Claim Reference Validation V2 workflow."""

import logging
from typing import List, Optional

from langchain_core.messages import BaseMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.agents.citation_validator import (
    CitationAssessment,
    CitationValidatorAgent,
    PartialSectionValidationError,
)
from lib.models.file import FileRole
from lib.workflows.claim_reference_validation_v2.citation_mapping import (
    build_reference_file_map,
)
from lib.services.document_sections import split_into_sections
from lib.workflows.claim_reference_validation_v2.state import (
    CitationIssueItem,
    ClaimReferenceValidationV2State,
    SectionVerificationItem,
    SectionVerificationStatus,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.error_details import capture_error_details
from lib.workflows.models import ErrorDetails, WorkflowError, WorkflowErrorSeverity

logger = logging.getLogger(__name__)


def _assessment_to_issue(assessment: CitationAssessment) -> CitationIssueItem:
    """Convert the agent's output record into the persisted workflow-state
    record. The deprecated `truthfulness_label` field is left unset (None)."""
    return CitationIssueItem(
        quoted_text=assessment.quoted_text,
        line_start=assessment.line_start,
        line_end=assessment.line_end,
        evidence_alignment=assessment.evidence_alignment,
        rationale=assessment.rationale,
        feedback=assessment.feedback,
        evidence_sources=assessment.evidence_sources,
        citation_to_file_mapping=assessment.citation_to_file_mapping,
    )


@register_node("Prepare sections")
async def prepare_sections(
    state: ClaimReferenceValidationV2State,
    runtime: Runtime[ContextSchema],
):
    """Split the main document into sections and initialise PENDING tracking items."""
    main_file = await runtime.context.file_artifacts_service.get_main_file()
    if not main_file or not main_file.markdown:
        logger.warning("No main file or markdown content found")
        return {"section_verifications": Overwrite([])}

    sections = split_into_sections(main_file.markdown)
    logger.info("Split document into %d sections", len(sections))

    pending = [
        SectionVerificationItem(
            section_index=s.section_index,
            start_line=s.start_line,
            end_line=s.end_line,
            headings=s.headings,
            status=SectionVerificationStatus.PENDING,
        )
        for s in sections
    ]

    return {"section_verifications": Overwrite(pending)}


@register_node("Distribute sections")
async def distribute_sections(
    state: ClaimReferenceValidationV2State,
    runtime: Runtime[ContextSchema],
):
    """Fan-out: create a Send for each pending section."""
    return [
        Send(
            "validate_section",
            {
                "section_index": item.section_index,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "headings": item.headings,
            },
        )
        for item in state.section_verifications
    ]


@register_node("Validate section")
async def validate_section(state: dict, runtime: Runtime[ContextSchema]):
    """Validate citations in a single document section."""
    section_index: int = state["section_index"]
    start_line: int = state["start_line"]
    end_line: int = state["end_line"]
    headings: List[str] = state.get("headings", [])

    file_artifacts_service = runtime.context.file_artifacts_service
    issues = []
    messages: List[BaseMessage] = []
    error: Optional[str] = None
    error_details: Optional[ErrorDetails] = None
    status = SectionVerificationStatus.COMPLETED

    try:
        main_file = await file_artifacts_service.get_main_file()
        references = await file_artifacts_service.get_references()
        supporting_files = await file_artifacts_service.get_project_files(
            [FileRole.SUPPORT]
        )

        reference_file_map = build_reference_file_map(references, supporting_files)

        headings_str = " > ".join(headings) if headings else "Document root"
        logger.info(
            "Validating section %d (lines %d-%d, headings: %s)",
            section_index,
            start_line,
            end_line,
            headings_str,
        )

        agent = CitationValidatorAgent(runtime.context)
        result, lc_messages = await agent.ainvoke(
            {
                "main_file_id": main_file.file_id,
                "start_line": start_line,
                "end_line": end_line,
                "section_headings": headings_str,
                "reference_file_map": reference_file_map,
                "headings": headings,
            }
        )

        issues = [_assessment_to_issue(a) for a in result.issues]
        messages = lc_messages

    except PartialSectionValidationError as e:
        # Keep what the model finished writing: a truncated response would
        # otherwise discard the whole section. The section stays flagged so the
        # gap is visible rather than silently under-reported.
        logger.warning(
            "Section %d returned truncated output; salvaged %d assessment(s): %s",
            section_index,
            len(e.result.issues),
            e,
        )
        issues = [_assessment_to_issue(a) for a in e.result.issues]
        messages = e.messages
        status = SectionVerificationStatus.PARTIAL
        error = str(e)
        error_details = capture_error_details(e)

    except Exception as e:
        logger.error("Error validating section %d: %s", section_index, e, exc_info=True)
        status = SectionVerificationStatus.ERROR
        error = str(e)
        # Persist the traceback and the raw model output alongside the message:
        # structured-output failures here are unreproducible after the fact, so
        # the state row is the only record of what the model actually returned.
        error_details = capture_error_details(e)

    return {
        "section_verifications": [
            SectionVerificationItem(
                section_index=section_index,
                start_line=start_line,
                end_line=end_line,
                headings=headings,
                status=status,
                num_citations=len(issues),
                issues=issues,
                error=error,
                error_details=error_details,
                messages=messages,
            )
        ]
    }


def _section_label(item: SectionVerificationItem) -> str:
    """Identify a section in user-facing text."""
    heading = " > ".join(item.headings) if item.headings else "Document root"
    return f"Section {item.section_index} ({heading}, lines {item.start_line}-{item.end_line})"


def _section_error_message(item: SectionVerificationItem) -> str:
    """State what the reader lost, not what the exception was.

    The underlying failure stays on `details` for debugging; a truncation is
    self-explanatory here, while a hard failure can have any cause, so its
    message is appended.
    """
    if item.status == SectionVerificationStatus.PARTIAL:
        return (
            f"{_section_label(item)} returned truncated output. "
            f"{len(item.issues)} citation assessment(s) were recovered; "
            "the rest are missing from these results."
        )

    return (
        f"{_section_label(item)} could not be validated. Its citations are "
        f"missing from these results. {item.error or 'Unknown error'}"
    )


@register_node("Finalize results")
async def finalize_results(
    state: ClaimReferenceValidationV2State,
    runtime: Runtime[ContextSchema],
):
    """Flatten section issues into the top-level citation_issues list."""
    all_issues = []
    errors: List[WorkflowError] = []

    # A failed section costs part of the document, not the run: the sections
    # that did complete still produced usable findings, so the run must not
    # read as failed. Only a run left with nothing usable escalates to an
    # error — otherwise an empty result set would render as an all-clear.
    produced_results = any(
        item.status
        in (SectionVerificationStatus.COMPLETED, SectionVerificationStatus.PARTIAL)
        for item in state.section_verifications
    )
    severity = (
        WorkflowErrorSeverity.WARNING
        if produced_results
        else WorkflowErrorSeverity.ERROR
    )

    for item in state.section_verifications:
        # PARTIAL sections contribute both: the assessments salvaged from a
        # truncated response, and the error explaining what was lost.
        if item.status in (
            SectionVerificationStatus.COMPLETED,
            SectionVerificationStatus.PARTIAL,
        ):
            all_issues.extend(item.issues)

        if item.status in (
            SectionVerificationStatus.ERROR,
            SectionVerificationStatus.PARTIAL,
        ):
            errors.append(
                WorkflowError(
                    task_name="validate_section",
                    error=_section_error_message(item),
                    workflow_run_id=runtime.context.workflow_run_id,
                    severity=severity,
                    details=item.error_details,
                )
            )

    return {"citation_issues": all_issues, "errors": errors}
