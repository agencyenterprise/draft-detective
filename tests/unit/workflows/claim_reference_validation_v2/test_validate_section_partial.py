"""Tests for how validate_section records a truncated model response."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from lib.agents.citation_validator import (
    CitationAssessment,
    PartialSectionValidationError,
    SectionValidationResult,
)
from lib.agents.claim_verifier import EvidenceAlignmentLevel
from lib.workflows.claim_reference_validation_v2.manifest import _build_issue
from lib.workflows.claim_reference_validation_v2.nodes import validate_sections
from lib.workflows.claim_reference_validation_v2.state import (
    SectionVerificationStatus,
)
from lib.workflows.models import WorkflowRunType

SECTION_INPUT = {
    "section_index": 8,
    "start_line": 89,
    "end_line": 99,
    "headings": ["Introduction"],
}


def _partial_error() -> PartialSectionValidationError:
    salvaged = SectionValidationResult(
        issues=[
            CitationAssessment(
                quoted_text="AI development is decentralized (The Economist, 2024).",
                line_start=91,
                line_end=91,
                evidence_alignment=EvidenceAlignmentLevel.SUPPORTED,
                rationale="The cited article describes competition among nations.",
                feedback="No changes needed",
            )
        ]
    )
    source = ValueError("Unterminated string starting at: line 1 column 2421")
    error = PartialSectionValidationError(salvaged, [AIMessage(content="{")], source)
    error.__cause__ = source
    return error


# The cited sentence sits on line 91, where the assessment says it does.
_MARKDOWN = "\n".join(
    ["Filler line."] * 90
    + ["Competition is fierce. AI development is decentralized (The Economist, 2024)."]
)


def _runtime() -> SimpleNamespace:
    file_artifacts_service = SimpleNamespace(
        get_main_file=AsyncMock(
            return_value=SimpleNamespace(file_id="main-file", markdown=_MARKDOWN)
        ),
        get_references=AsyncMock(return_value=[]),
        get_project_files=AsyncMock(return_value=[]),
    )
    return SimpleNamespace(
        context=SimpleNamespace(
            file_artifacts_service=file_artifacts_service,
            workflow_run_id="run-1",
        )
    )


async def _validate_section_raising(error: Exception) -> dict:
    agent = SimpleNamespace(ainvoke=AsyncMock(side_effect=error))
    with patch.object(validate_sections, "CitationValidatorAgent", return_value=agent):
        return await validate_sections.validate_section.__wrapped__(
            dict(SECTION_INPUT), _runtime()
        )


@pytest.mark.asyncio
async def test_truncated_response_is_recorded_as_partial_with_its_issues():
    result = await _validate_section_raising(_partial_error())

    item = result["section_verifications"][0]
    assert item.status == SectionVerificationStatus.PARTIAL
    assert item.section_index == 8
    assert item.num_citations == 1
    assert item.issues[0].quoted_text.startswith("AI development is decentralized")
    # The cited text is located as the issue's passage, on its own line.
    passage = item.issues[0].passage
    assert passage is not None
    assert passage.start_line == 91
    assert passage.display_text == (
        "AI development is decentralized (The Economist, 2024)."
    )


@pytest.mark.asyncio
async def test_partial_section_keeps_the_error_and_its_diagnostics():
    result = await _validate_section_raising(_partial_error())

    item = result["section_verifications"][0]
    assert item.error is not None
    assert "recovered 1 complete citation assessment(s)" in item.error
    assert item.error_details is not None
    assert item.error_details.error_type == "PartialSectionValidationError"
    assert item.error_details.traceback is not None


@pytest.mark.asyncio
async def test_unsalvageable_failure_is_still_a_hard_error():
    result = await _validate_section_raising(RuntimeError("boom"))

    item = result["section_verifications"][0]
    assert item.status == SectionVerificationStatus.ERROR
    assert item.issues == []
    assert item.error == "boom"
    assert item.error_details is not None
    assert item.error_details.error_type == "RuntimeError"


def test_the_located_cited_text_becomes_the_issue_passage():
    lines = _MARKDOWN.split("\n")
    assessment = _partial_error().result.issues[0]

    located = validate_sections._assessment_to_issue(assessment, lines)
    issue = _build_issue(located, None, WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2)
    assert issue is not None
    assert issue.passage == located.passage

    elsewhere = assessment.model_copy(update={"line_start": 1, "line_end": 1})
    assert validate_sections._assessment_to_issue(elsewhere, lines).passage is None
