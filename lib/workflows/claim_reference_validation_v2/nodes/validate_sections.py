"""Graph nodes for Claim Reference Validation V2 workflow."""

import logging
from typing import List, Optional

from langgraph.runtime import Runtime
from langgraph.types import Overwrite, Send

from lib.agents.citation_validator import CitationValidatorAgent
from lib.agents.formatting_utils import format_audience_context, format_domain_context
from lib.workflows.claim_reference_validation_v2.citation_mapping import (
    build_reference_file_map,
)
from lib.workflows.claim_reference_validation_v2.sections import split_into_sections
from lib.workflows.claim_reference_validation_v2.state import (
    ClaimReferenceValidationV2State,
    SectionVerificationItem,
    SectionVerificationStatus,
)
from lib.workflows.context import ContextSchema
from lib.workflows.decorators import register_node
from lib.workflows.models import WorkflowError

logger = logging.getLogger(__name__)


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
                "domain": state.config.domain,
                "target_audience": state.config.target_audience,
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
    domain: Optional[str] = state.get("domain")
    target_audience: Optional[str] = state.get("target_audience")

    file_artifacts_service = runtime.context.file_artifacts_service
    issues = []
    error: Optional[str] = None
    status = SectionVerificationStatus.COMPLETED

    try:
        main_file = await file_artifacts_service.get_main_file()
        references = await file_artifacts_service.get_references()
        supporting_files = await file_artifacts_service.get_supporting_files()

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
        result = await agent.ainvoke(
            {
                "main_file_id": main_file.file_id,
                "start_line": start_line,
                "end_line": end_line,
                "section_headings": headings_str,
                "reference_file_map": reference_file_map,
                "domain_context": format_domain_context(domain),
                "audience_context": format_audience_context(target_audience),
                "headings": headings,
            }
        )

        issues = result.issues

    except Exception as e:
        logger.error("Error validating section %d: %s", section_index, e, exc_info=True)
        status = SectionVerificationStatus.ERROR
        error = str(e)

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
            )
        ]
    }


@register_node("Finalize results")
async def finalize_results(
    state: ClaimReferenceValidationV2State,
    runtime: Runtime[ContextSchema],
):
    """Flatten section issues into the top-level citation_issues list."""
    all_issues = []
    errors: List[WorkflowError] = []

    for item in state.section_verifications:
        if item.status == SectionVerificationStatus.COMPLETED:
            all_issues.extend(item.issues)
        elif item.status == SectionVerificationStatus.ERROR:
            errors.append(
                WorkflowError(
                    task_name="validate_section",
                    error=item.error or "Unknown error",
                    workflow_run_id=runtime.context.workflow_run_id,
                )
            )

    return {"citation_issues": all_issues, "errors": errors}
