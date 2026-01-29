import asyncio
from pathlib import Path
from typing import Any, Dict, List

import pytest

from lib.agents.document_chunker_nltk import (
    DocumentChunkerResponse,
    DocumentChunkerAgent,
)
from tests.conftest import (
    create_test_file_document_from_path,
    data_path,
    create_test_context,
)
from tests.evals.datasets.loader import load_dataset

TESTS_DIR = Path(__file__).parent.parent.parent


def _extract_text_from_chunks(response: DocumentChunkerResponse) -> Dict[str, Any]:
    """
    Extract only text content from chunks for comparison.

    This normalizes the response to match the expected format in YAML,
    ignoring line numbers which are not specified in test data.
    """
    return {
        "paragraphs": [
            {
                "chunks": [chunk.text for chunk in paragraph.chunks],
                "headings": paragraph.headings,
            }
            for paragraph in response.paragraphs
        ]
    }


def _build_test_data() -> List[Dict[str, Any]]:
    """Load test cases from YAML dataset."""
    dataset_path = str(TESTS_DIR / "datasets" / "document_chunker_nltk.yaml")
    dataset = load_dataset(dataset_path)

    test_data = []
    for test_case in dataset.items:
        main_path = data_path(test_case.input["main_document"])
        main_doc = asyncio.run(create_test_file_document_from_path(main_path))

        test_data.append(
            {
                "name": test_case.name,
                "markdown": main_doc.markdown,
                "expected": test_case.expected_output,
            }
        )

    return test_data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data", _build_test_data(), ids=lambda d: d["name"]
)
async def test_document_chunker_nltk_agent_cases(test_data):
    """Test document chunker produces correct text chunks.

    Line numbers are tracked but not compared - only text content and headings matter.
    """
    agent = DocumentChunkerAgent(create_test_context())
    result = await agent.ainvoke(prompt_kwargs={"full_document": test_data["markdown"]})

    # Extract text content for comparison (ignoring line numbers)
    actual = _extract_text_from_chunks(result)
    expected = test_data["expected"]

    # Compare paragraph by paragraph
    assert len(actual["paragraphs"]) == len(expected["paragraphs"]), (
        f"Paragraph count mismatch: got {len(actual['paragraphs'])}, "
        f"expected {len(expected['paragraphs'])}"
    )

    for i, (act_para, exp_para) in enumerate(
        zip(actual["paragraphs"], expected["paragraphs"])
    ):
        assert act_para["headings"] == exp_para["headings"], (
            f"Paragraph {i} headings mismatch:\n"
            f"  got: {act_para['headings']}\n"
            f"  expected: {exp_para['headings']}"
        )
        assert act_para["chunks"] == exp_para["chunks"], (
            f"Paragraph {i} chunks mismatch:\n"
            f"  got: {act_para['chunks']}\n"
            f"  expected: {exp_para['chunks']}"
        )
