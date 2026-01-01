"""Tests for reference extraction workflow."""

import logging

import pytest
import yaml
from rapidfuzz import fuzz

from lib.models.bibliography_item import BibliographyItem
from lib.services.file import FileDocument
from lib.workflows.document_processing.graph import build_document_processing_graph
from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.reference_extraction.graph import build_reference_extraction_graph
from lib.workflows.reference_extraction.state import (
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


async def run_workflow(graph_builder, state):
    """Run a workflow graph with test context."""
    return await graph_builder().compile().ainvoke(state, context=create_test_context())


async def run_full_pipeline(
    file: FileDocument, supporting_files: list[FileDocument] | None = None
) -> dict:
    """Run document processing → reference extraction pipeline."""
    doc_state = DocumentProcessingState(
        config=DocumentProcessingWorkflowConfig(project_id="test"),
        file=file,
        supporting_files=supporting_files,
    )
    doc_result = await run_workflow(build_document_processing_graph, doc_state)

    ref_state = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id="test"),
        file=doc_result["file"],
        supporting_files=doc_result.get("supporting_files"),
        supporting_documents_summaries=doc_result.get("supporting_documents_summaries"),
    )
    return await run_workflow(build_reference_extraction_graph, ref_state)


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
        data_path("data/case_1/main_document.md")
    )
    result = await run_full_pipeline(file)

    assert len(result["detected_sections"]) >= 1
    assert len(result["references"]) >= 1

    for section in result["detected_sections"]:
        assert isinstance(section, ReferenceSection)
        assert section.end_offset > section.start_offset >= 0

    for ref in result["references"]:
        assert isinstance(ref, BibliographyItem)
        assert ref.text


@pytest.mark.asyncio
async def test_reference_extraction_with_supporting_docs():
    main_file = await create_test_file_document_from_path(
        data_path("data/case_1/main_document.md")
    )
    supporting_file = await create_test_file_document_from_path(
        data_path("data/case_1/supporting_1.md")
    )

    result = await run_full_pipeline(main_file, [supporting_file])

    assert len(result["references"]) >= 1
    for ref in result["references"]:
        assert isinstance(ref.has_associated_supporting_document, bool)
        assert isinstance(ref.index_of_associated_supporting_document, int)
        assert isinstance(ref.name_of_associated_supporting_document, str)


@pytest.mark.asyncio
async def test_empty_document_no_references():
    file = FileDocument(
        file_name="empty.md",
        file_path="empty.md",
        file_type="text/markdown",
        markdown="# Introduction\n\nThis document has no references section.",
        markdown_token_count=10,
    )

    state = ReferenceExtractionState(
        config=ReferenceExtractionConfig(project_id="test"), file=file
    )
    result = await run_workflow(build_reference_extraction_graph, state)

    assert result["references"] == []
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
        data_path(f"data/reference_extraction_stress_test/{doc_filename}")
    )
    result = await run_full_pipeline(file)

    assert len(result["detected_sections"]) >= 1

    yaml_path = data_path(f"data/reference_extraction_stress_test/{expected_yaml}")
    with open(yaml_path) as f:
        expected_refs = yaml.safe_load(f)["references"]

    extracted_reference_texts = [r.text for r in result["references"]]
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
