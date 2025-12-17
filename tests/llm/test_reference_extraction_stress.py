"""
Test reference extraction stress test cases.

This test validates reference extraction on large documents by:
1. Loading expected references from JSON files
2. Running the reference extractor on corresponding documents
3. Selecting random references from expected list
4. Fuzzy matching them against actual extracted references

Costs are tracked via Langfuse through the RunnableConfig passed to agents.
"""

import json
import logging
import random
import time
from typing import NamedTuple

import pytest
from langchain_core.runnables.config import RunnableConfig
from rapidfuzz import fuzz

from lib.agents.reference_extractor import ReferenceExtractorAgent
from tests.conftest import (
    create_test_context,
    create_test_file_document_from_path,
    data_path,
)

logger = logging.getLogger(__name__)

FUZZY_MATCH_THRESHOLD = 71
NUM_SAMPLE_REFERENCES = 3
RANDOM_SEED = 42


class TestCase(NamedTuple):
    """Test case configuration for reference extraction."""

    name: str
    doc_filename: str
    expected_refs_filename: str


TEST_CASES = [
    TestCase(
        name="RAND_RRA4036-1",
        doc_filename="RAND_RRA4036-1.md",
        expected_refs_filename="expected_references_RAND_RRA4036-1.json",
    ),
    TestCase(
        name="RAND_RRA4636-1",
        doc_filename="RAND_RRA4636-1.md",
        expected_refs_filename="expected_references_RAND_RRA4636-1.json",
    ),
]


@pytest.fixture
def reference_extractor():
    """Create reference extractor agent for testing."""
    return ReferenceExtractorAgent(create_test_context())


def load_expected_references(json_filename: str) -> list[str]:
    """Load expected references from JSON file."""
    json_path = data_path(f"data/reference_extraction_stress_test/{json_filename}")
    with open(json_path, "r") as f:
        return json.load(f)["references"]


def find_best_fuzzy_match(target: str, candidates: list[str]) -> tuple[str, float]:
    """Find the best fuzzy match for target string in candidates list."""
    if not candidates:
        return "", 0.0

    best_match = ""
    best_score = 0.0

    for candidate in candidates:
        score = fuzz.ratio(target.lower(), candidate.lower())
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match, best_score


def validate_sample_references(sample_refs: list[str], actual_refs: list[str]) -> None:
    """Validate sample references against actual extracted references."""
    for idx, expected_ref in enumerate(sample_refs, 1):
        best_match, similarity = find_best_fuzzy_match(expected_ref, actual_refs)

        if similarity >= FUZZY_MATCH_THRESHOLD:
            logger.info(f"[{idx}/{len(sample_refs)}] ✓ {similarity:.1f}%")
        else:
            logger.error(f"[{idx}/{len(sample_refs)}] ✗ {similarity:.1f}%")
            logger.error(f"Expected: {expected_ref[:100]}...")
            logger.error(f"Best match: {best_match[:100]}...")
            assert False, (
                f"Reference match failed (similarity: {similarity:.1f}%, "
                f"threshold: {FUZZY_MATCH_THRESHOLD}%)\n"
                f"Expected: {expected_ref[:200]}...\n"
                f"Best match: {best_match[:200]}..."
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: tc.name)
async def test_reference_extraction(reference_extractor, test_case: TestCase):
    """Test reference extraction on large documents with fuzzy matching."""
    logger.info(f"{'=' * 80}")
    logger.info(f"Test: {test_case.name}")

    # Load expected references and select random samples
    expected_refs = load_expected_references(test_case.expected_refs_filename)
    random.seed(RANDOM_SEED)
    sample_refs = random.sample(
        expected_refs, min(NUM_SAMPLE_REFERENCES, len(expected_refs))
    )
    logger.info(f"Testing {len(sample_refs)}/{len(expected_refs)} random references")

    # Load document
    doc_path = data_path(
        f"data/reference_extraction_stress_test/{test_case.doc_filename}"
    )
    doc = await create_test_file_document_from_path(doc_path)
    logger.info(f"Document: {len(doc.markdown):,} chars")

    # Extract references with timing and Langfuse tracing
    start_time = time.time()
    config = RunnableConfig(
        run_name=f"reference_extraction_stress_test_{test_case.name}",
        metadata={
            "test_name": test_case.name,
            "doc_filename": test_case.doc_filename,
            "doc_length": len(doc.markdown),
        },
    )

    try:
        result = await reference_extractor.ainvoke(
            {
                "full_document": doc.markdown,
                "supporting_documents": "No supporting documents provided.",
            },
            config=config,
        )
        elapsed = time.time() - start_time
        logger.info(f"Extracted {len(result.references)} references in {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Extraction failed after {elapsed:.2f}s: {e}", exc_info=True)
        raise

    # Validate fuzzy matching
    actual_refs = [ref.text for ref in result.references]
    validate_sample_references(sample_refs, actual_refs)
    logger.info(f"{'=' * 80}")
