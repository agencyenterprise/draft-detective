"""Tests for reference extraction workflow."""

import pytest

from lib.workflows.document_processing.state import (
    DocumentProcessingState,
    DocumentProcessingWorkflowConfig,
)
from lib.workflows.reference_extraction.graph import build_reference_extraction_graph
from lib.workflows.reference_extraction.state import (
    ReferenceExtractionConfig,
    ReferenceExtractionState,
)
from tests.conftest import (
    create_test_context,
    create_test_file_document_from_path,
    data_path,
)


@pytest.mark.asyncio
async def test_reference_extraction_workflow_basic():
    """Test basic reference extraction workflow with section detection."""
    # Create test document
    file = await create_test_file_document_from_path(
        data_path("data/case_1/main_document.md")
    )

    # Create minimal document processing state (simulating dependency)
    doc_processing_state = DocumentProcessingState(
        config=DocumentProcessingWorkflowConfig(project_id="test"),
        file=file,
        chunks=[],  # Would normally have chunks, but not needed for this test
    )

    # Create config and state
    config = ReferenceExtractionConfig(project_id="test")
    state = ReferenceExtractionState(
        config=config,
        file=doc_processing_state.file,
        chunks=doc_processing_state.chunks,
        supporting_files=None,
    )

    # Build and run graph
    graph = build_reference_extraction_graph()
    context = create_test_context()

    app = graph.compile()
    result = await app.ainvoke(state, context=context)

    # Verify results
    assert "references" in result
    assert isinstance(result["references"], list)
    assert "detected_sections" in result
    assert isinstance(result["detected_sections"], list)


@pytest.mark.asyncio
async def test_reference_extraction_with_supporting_docs():
    """Test reference extraction with supporting documents."""
    # Create test documents
    main_file = await create_test_file_document_from_path(
        data_path("data/case_1/main_document.md")
    )
    supporting_file = await create_test_file_document_from_path(
        data_path("data/case_1/supporting_1.md")
    )

    # Create config and state
    config = ReferenceExtractionConfig(project_id="test")
    state = ReferenceExtractionState(
        config=config,
        file=main_file,
        chunks=[],
        supporting_files=[supporting_file],
    )

    # Build and run graph
    graph = build_reference_extraction_graph()
    context = create_test_context()

    app = graph.compile()
    result = await app.ainvoke(state, context=context)

    # Verify results
    assert "references" in result
    assert isinstance(result["references"], list)


@pytest.mark.asyncio
async def test_reference_extraction_empty_document():
    """Test reference extraction with document that has no references."""
    from lib.services.file import FileDocument

    file = FileDocument(
        file_name="test.md",
        file_path="/tmp/test.md",
        file_type="text/markdown",
        markdown="# Test Document\n\nThis has no references.",
        markdown_token_count=10,
    )

    # Create config and state
    config = ReferenceExtractionConfig(project_id="test")
    state = ReferenceExtractionState(
        config=config,
        file=file,
        chunks=[],
        supporting_files=None,
    )

    # Build and run graph
    graph = build_reference_extraction_graph()
    context = create_test_context()

    app = graph.compile()
    result = await app.ainvoke(state, context=context)

    # Verify results - should handle gracefully
    assert "references" in result
    assert isinstance(result["references"], list)
    assert "detected_sections" in result

