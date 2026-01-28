"""Tests for reference extraction workflow."""

import logging

import pytest
import yaml
from rapidfuzz import fuzz

from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from lib.workflows.context import ContextSchema
from lib.workflows.document_processing.graph import build_document_processing_graph
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.models import WorkflowRunType
from lib.workflows.reference_extraction.graph import build_reference_extraction_graph
from lib.workflows.reference_extraction.state import (
    ExtractedReference,
    ReferenceExtractionConfig,
    ReferenceExtractionState,
    ReferenceSection,
)
from tests.conftest import (
    create_test_context,
    create_test_file_document_from_path,
    data_path,
)

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 85
MIN_STRESS_MATCH_RATE = 95

STRESS_TEST_CASES = [
    ("RAND_RRA4036-1", "RAND_RRA4036-1.md", "expected_RAND_RRA4036-1.yaml"),
    ("RAND_RRA4636-1", "RAND_RRA4636-1.md", "expected_RAND_RRA4636-1.yaml"),
]


def create_context_with_file(main_file: FileDocument) -> ContextSchema:
    """Create a context with a mock file_artifacts_service configured with the file."""

    return create_test_context(
        file_artifacts_service=MockFileArtifactsService(main_file=main_file)
    )


async def run_full_pipeline(file: FileDocument) -> dict:
    """Run document processing → reference extraction pipeline."""
    # Run document processing first to get the processed file
    doc_state = DocumentProcessingState(
        type=WorkflowRunType.DOCUMENT_PROCESSING,
        config=DocumentProcessingWorkflowConfig(
            type=WorkflowRunType.DOCUMENT_PROCESSING, project_id="test"
        ),
        file=file,
    )
    doc_result = (
        await build_document_processing_graph()
        .compile()
        .ainvoke(doc_state, context=create_test_context())
    )

    # Create context with the processed file so reference extraction can access it
    processed_file = doc_result["file"]
    context = create_context_with_file(processed_file)

    ref_state = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id="test"),
        file_id=processed_file.file_id,
    )
    return (
        await build_reference_extraction_graph()
        .compile()
        .ainvoke(ref_state, context=context)
    )


def validate_references(expected: list[str], extracted: list[str]) -> tuple[int, list]:
    """Return (matched_count, missing_refs) using fuzzy matching."""
    matched, missing = 0, []
    for ref in expected:
        best_score = max(
            (fuzz.ratio(ref.lower(), e.lower()) for e in extracted), default=0
        )
        if best_score >= FUZZY_MATCH_THRESHOLD:
            matched += 1
        else:
            missing.append(ref[:100] + "..." if len(ref) > 100 else ref)
    return matched, missing


@pytest.mark.asyncio
async def test_basic_reference_extraction():
    file = await create_test_file_document_from_path(
        "evals/data/case_1/main_document.md"
    )
    result = await run_full_pipeline(file)

    assert len(result["detected_sections"]) >= 1
    assert len(result["extracted_references"]) >= 1

    for section in result["detected_sections"]:
        assert isinstance(section, ReferenceSection)
        assert section.end_offset > section.start_offset >= 0

    for ref in result["extracted_references"]:
        assert isinstance(ref, ExtractedReference)
        assert ref.id  # Should have a unique ID
        assert ref.text


@pytest.mark.asyncio
async def test_empty_document_no_references():
    file = FileDocument(
        file_id="empty.md",
        file_name="empty.md",
        file_path="empty.md",
        file_type="text/markdown",
        markdown="# Introduction\n\nThis document has no references section.",
        markdown_token_count=10,
    )

    context = create_context_with_file(file)
    state = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id="test"),
        file_id=file.file_id,
    )
    result = (
        await build_reference_extraction_graph()
        .compile()
        .ainvoke(state, context=context)
    )

    assert result["extracted_references"] == []
    assert result["detected_sections"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "doc_name,doc_filename,expected_yaml",
    STRESS_TEST_CASES,
    ids=[tc[0] for tc in STRESS_TEST_CASES],
)
async def test_stress_large_document(
    doc_name: str, doc_filename: str, expected_yaml: str
):
    file = await create_test_file_document_from_path(
        f"evals/data/reference_extraction_stress_test/{doc_filename}"
    )
    result = await run_full_pipeline(file)

    assert len(result["detected_sections"]) >= 1

    yaml_path = data_path(f"data/reference_extraction_stress_test/{expected_yaml}")
    with open(yaml_path) as f:
        expected_refs = yaml.safe_load(f)["references"]

    extracted_reference_texts = [r.text for r in result["extracted_references"]]
    matched, missing = validate_references(expected_refs, extracted_reference_texts)
    match_rate = matched / len(expected_refs) * 100

    logger.info(
        f"{doc_name}: {matched}/{len(expected_refs)} refs ({match_rate:.1f}%), "
        f"extracted {len(extracted_reference_texts)} total"
    )

    assert match_rate >= MIN_STRESS_MATCH_RATE, (
        f"{doc_name}: {match_rate:.1f}% matched (need {MIN_STRESS_MATCH_RATE}%). "
        f"Missing: {missing[:5]}{'...' if len(missing) > 5 else ''}"
    )

    assert len(set(extracted_reference_texts)) == len(
        extracted_reference_texts
    ), "Found duplicate references"
