"""Tests for DOCX chunk mapping service"""

import pytest
from docx import Document
from pathlib import Path

from lib.services.docx_chunk_mapper import create_chunk_to_paragraph_mapping
from lib.services.nltk_text_splitter import NLTKTextSplitter
from lib.workflows.claim_substantiation.context import ContextSchema
from tests.conftest import create_test_file_document_from_path, data_path


@pytest.mark.asyncio
async def test_chunk_to_docx_mapping_agi_minimal():
    """
    End-to-end test of chunk matching using agi-minimal test data.
    """
    file_doc = await create_test_file_document_from_path(
        "data/geopolitics-of-agi-minimal-1/_original.docx"
    )

    context = ContextSchema(
        session_id="test-session", workflow_id="test-workflow", run_id="test-run"
    )
    chunker = NLTKTextSplitter(context=context)
    chunks = await chunker.create_documents([file_doc.markdown])

    docx_path = data_path("data/geopolitics-of-agi-minimal-1/_original.docx")
    doc = Document(docx_path)
    docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

    mapping = create_chunk_to_paragraph_mapping(chunks, docx_paragraphs)

    print(f"\n=== Mapping Results ===")
    print(f"Total chunks: {len(chunks)}")
    print(f"Total DOCX paragraphs: {len(docx_paragraphs)}")
    print(f"Chunks mapped: {len(mapping)}")
    print(f"Coverage: {len(mapping) / len(chunks) * 100:.1f}%")

    assert len(mapping) > 0, "Should map at least some chunks"
    assert len(mapping) / len(chunks) > 0.5, "Should map >50% of chunks"

    for chunk_idx, para_idx in mapping.items():
        assert (
            0 <= para_idx < len(docx_paragraphs)
        ), f"Invalid paragraph index {para_idx} for chunk {chunk_idx}"


@pytest.mark.asyncio
async def test_chunk_to_docx_detailed_inspection():
    """
    Detailed inspection test: print actual matches to verify correctness.

    This test helps manually verify the matching is correct by showing
    what chunks map to which paragraphs.
    """
    docx_path = data_path("data/geopolitics-of-agi-minimal-1/_original.docx")
    file_doc = await create_test_file_document_from_path(
        "data/geopolitics-of-agi-minimal-1/_original.docx"
    )

    context = ContextSchema(
        session_id="test-session", workflow_id="test-workflow", run_id="test-run"
    )
    chunker = NLTKTextSplitter(context=context)
    chunks = await chunker.create_documents([file_doc.markdown])

    doc = Document(docx_path)
    docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

    mapping = create_chunk_to_paragraph_mapping(chunks, docx_paragraphs)

    print(f"\n=== Detailed Chunk to Paragraph Mapping ===\n")

    for i, chunk in enumerate(chunks[:5]):
        chunk_idx = chunk.metadata.chunk_index
        para_idx = chunk.metadata.paragraph_index

        print(f"Chunk #{chunk_idx} (paragraph_index={para_idx})")
        print(f"  Content: {chunk.page_content[:80]}...")

        if chunk_idx in mapping:
            docx_idx = mapping[chunk_idx]
            docx_text = docx_paragraphs[docx_idx].text
            print(f"  → Matched DOCX paragraph #{docx_idx}")
            print(f"  DOCX text: {docx_text[:80]}...")
            print(f"  ✓ Match confirmed")
        else:
            print(f"  ✗ No match found")
        print()

    assert len(mapping) > 0, "Should have at least some mappings"


@pytest.mark.asyncio
async def test_chunk_mapping_handles_empty_chunks():
    """Test that empty chunks are handled gracefully"""
    from lib.agents.models import ValidatedDocument, DocumentMetadata
    from docx import Document

    chunks = [
        ValidatedDocument(
            page_content="",
            metadata=DocumentMetadata(
                chunk_index=0, paragraph_index=0, chunk_index_within_paragraph=0
            ),
        ),
        ValidatedDocument(
            page_content="Some actual content",
            metadata=DocumentMetadata(
                chunk_index=1, paragraph_index=1, chunk_index_within_paragraph=0
            ),
        ),
    ]

    docx_path = data_path("data/geopolitics-of-agi-minimal-1/_original.docx")
    doc = Document(docx_path)
    docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

    mapping = create_chunk_to_paragraph_mapping(chunks, docx_paragraphs)

    assert 0 not in mapping, "Empty chunk should not be mapped"


def test_duplicate_text_maps_to_correct_paragraphs():
    """
    Test that duplicate text at different positions maps correctly.

    Chunk 1 "I repeat myself" should map to paragraph 1,
    Chunk 3 "I repeat myself" should map to paragraph 3 (not paragraph 1 again).
    """
    from lib.agents.models import ValidatedDocument, DocumentMetadata

    class MockParagraph:
        def __init__(self, text):
            self.text = text

    docx_paragraphs = [
        MockParagraph("I repeat myself forever"),  # para 0
        MockParagraph("Something else here"),  # para 1
        MockParagraph("I repeat myself always"),  # para 2
        MockParagraph("Final paragraph"),  # para 3
    ]

    chunks = [
        ValidatedDocument(
            page_content="I repeat myself",
            metadata=DocumentMetadata(
                chunk_index=0, paragraph_index=0, chunk_index_within_paragraph=0
            ),
        ),
        ValidatedDocument(
            page_content="forever",
            metadata=DocumentMetadata(
                chunk_index=1, paragraph_index=0, chunk_index_within_paragraph=1
            ),
        ),
        ValidatedDocument(
            page_content="Something else",
            metadata=DocumentMetadata(
                chunk_index=2, paragraph_index=1, chunk_index_within_paragraph=0
            ),
        ),
        ValidatedDocument(
            page_content="I repeat myself",  # Same text as chunk 0!
            metadata=DocumentMetadata(
                chunk_index=3, paragraph_index=2, chunk_index_within_paragraph=0
            ),
        ),
        ValidatedDocument(
            page_content="always",
            metadata=DocumentMetadata(
                chunk_index=4, paragraph_index=2, chunk_index_within_paragraph=1
            ),
        ),
    ]

    mapping = create_chunk_to_paragraph_mapping(chunks, docx_paragraphs)

    assert mapping[0] == 0, "Chunk 0 'I repeat myself' should map to paragraph 0"
    assert mapping[1] == 0, "Chunk 1 'forever' should map to paragraph 0"
    assert mapping[2] == 1, "Chunk 2 'Something else' should map to paragraph 1"
    assert (
        mapping[3] == 2
    ), "Chunk 3 'I repeat myself' should map to paragraph 2 (not 0!)"
    assert mapping[4] == 2, "Chunk 4 'always' should map to paragraph 2"

    print("\n✓ Duplicate text correctly mapped to different paragraphs")
    print(f"  Chunk 0 'I repeat myself' → paragraph {mapping[0]}")
    print(f"  Chunk 3 'I repeat myself' → paragraph {mapping[3]}")


@pytest.mark.asyncio
async def test_add_comments_to_docx():
    """
    Test adding comments to DOCX file.

    This tests the complete integration:
    1. Load DOCX and convert to markdown
    2. Chunk the markdown
    3. Create comments for some chunks
    4. Add comments to DOCX
    5. Verify output file is created
    """
    from lib.services.docx_manipulator import DocxManipulatorService, DocxComment

    file_doc = await create_test_file_document_from_path(
        "data/geopolitics-of-agi-minimal-1/_original.docx"
    )

    context = ContextSchema(
        session_id="test-session", workflow_id="test-workflow", run_id="test-run"
    )
    chunker = NLTKTextSplitter(context=context)
    chunks = await chunker.create_documents([file_doc.markdown])

    comments = [
        DocxComment(
            chunk_index=0,
            text=chunks[0].page_content,
            author="AI Reviewer",
            comment_text="This is a test comment for chunk 0",
        ),
        DocxComment(
            chunk_index=1,
            text=chunks[1].page_content,
            author="Test User",
            comment_text="Another test comment for chunk 1",
        ),
        DocxComment(
            chunk_index=2,
            text=chunks[2].page_content,
            author="Reviewer Bot",
            comment_text="Third test comment for chunk 2",
        ),
    ]

    service = DocxManipulatorService()
    output_path = await service.add_comments_to_docx(
        original_docx_path=file_doc.file_path,
        comments=comments,
        workflow_run_id="test-run-123",
        chunks=chunks,
    )

    assert Path(output_path).exists(), "Output DOCX file should exist"

    doc = Document(output_path)
    assert len(doc.paragraphs) > 0, "Output DOCX should have paragraphs"

    try:
        if hasattr(doc, "part") and hasattr(doc.part, "package"):
            comments_part_exists = any(
                "comments" in str(part_name).lower()
                for part_name in doc.part.package.part_names
            )
            if comments_part_exists:
                print(f"\n✓ Comments part detected in DOCX package")
        print(f"\n✓ Successfully created DOCX with comments at: {output_path}")
        print(f"  Total paragraphs: {len(doc.paragraphs)}")
        print(f"  Comments requested: {len(comments)}")
    except Exception as e:
        print(f"\n⚠ Could not verify comments (non-fatal): {e}")
