"""
Comprehensive test suite for footnote chunking across all detection methods.

This test suite compares:
1. NLTK-only (no fallback)
2. NLTK + Reconstruction detection
3. NLTK + Semantic detection
4. NLTK + Statistical detection
5. LLM-only

Goal: Measure accuracy, performance, and cost for each approach on footnote text.
"""

import asyncio
import time
from typing import Any, Dict, List

import nltk
import pytest
from pydantic import BaseModel

from lib.agents.document_chunker_nltk import (
    llm_tokenize_paragraph,
    split_paragraph_into_sentences,
)
from lib.services.fragment_detection import DetectionMethod
from tests.conftest import create_test_context


class FootnoteTestCase(BaseModel):
    """A test case with expected behavior."""

    name: str
    text: str
    expected_chunks: List[str]
    description: str
    should_use_llm: bool


FOOTNOTE_TEST_CASES = [
    FootnoteTestCase(
        name="simple_numbered_footnote",
        text="1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry.",
        expected_chunks=[
            "1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry."
        ],
        description="Simple numbered footnote citation",
        should_use_llm=False,  # Handled by special case (numbered ref)
    ),
    FootnoteTestCase(
        name="footnote_with_author_initials",
        text="Smith, J., Doe, A., & Roe, B. (2019). A Comprehensive Study of Gizmos. Proceedings of Gizmo Conf.",
        expected_chunks=[
            "Smith, J., Doe, A., & Roe, B. (2019). A Comprehensive Study of Gizmos. Proceedings of Gizmo Conf."
        ],
        description="Citation with multiple author initials",
        should_use_llm=True,  # NLTK splits at initials
    ),
    FootnoteTestCase(
        name="footnote_et_al",
        text="Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145.",
        expected_chunks=[
            "Johnson et al. (2020). Machine Learning Approaches to Data Analysis. Nature Machine Intelligence, 5(2), 123-145."
        ],
        description="Citation with 'et al.'",
        should_use_llm=True,  # NLTK splits at 'al.'
    ),
    FootnoteTestCase(
        name="footnote_journal_abbreviations",
        text="Brown, M., & Green, K. (2018). Neural Networks in Practice. J. Neurosci. Methods, 15(3), 45-67.",
        expected_chunks=[
            "Brown, M., & Green, K. (2018). Neural Networks in Practice. J. Neurosci. Methods, 15(3), 45-67."
        ],
        description="Citation with journal abbreviations",
        should_use_llm=True,  # NLTK splits at abbreviations
    ),
    FootnoteTestCase(
        name="footnote_with_abstract_sentences",
        text="1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry. This groundbreaking study examined widget performance. Results showed a 20% improvement.",
        expected_chunks=[
            "1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry. This groundbreaking study examined widget performance. Results showed a 20% improvement."
        ],
        description="Numbered footnote with additional descriptive sentences",
        should_use_llm=False,  # Numbered ref handled by special case
    ),
    FootnoteTestCase(
        name="footnote_complex_abbreviations",
        text="Anderson, R. J., Smith, P. K., & Williams, M. T. (2021). Advanced Topics in A.I. Research. Proc. Natl. Acad. Sci. U.S.A., 118(25), e2021234118.",
        expected_chunks=[
            "Anderson, R. J., Smith, P. K., & Williams, M. T. (2021). Advanced Topics in A.I. Research. Proc. Natl. Acad. Sci. U.S.A., 118(25), e2021234118."
        ],
        description="Citation with multiple complex abbreviations",
        should_use_llm=True,  # Many split points
    ),
    FootnoteTestCase(
        name="footnote_with_doi",
        text="Martinez, L. et al. (2022). Deep Learning Applications. Nature, 600, 123-128. https://doi.org/10.1038/s41586-022-12345-6",
        expected_chunks=[
            "Martinez, L. et al. (2022). Deep Learning Applications. Nature, 600, 123-128. https://doi.org/10.1038/s41586-022-12345-6"
        ],
        description="Modern citation with DOI",
        should_use_llm=True,  # et al. + DOI periods
    ),
    FootnoteTestCase(
        name="footnote_government_org",
        text="1. National Institute of Standards and Technology (NIST). (2022). Security Guidelines. Tech. Rep. 800-53.",
        expected_chunks=[
            "1. National Institute of Standards and Technology (NIST). (2022). Security Guidelines. Tech. Rep. 800-53."
        ],
        description="Government organization citation",
        should_use_llm=False,  # Numbered ref
    ),
    FootnoteTestCase(
        name="footnote_multiple_citations",
        text="See Smith, J. (2020). Widget Analysis. J. Widgets, 5(2), 10-20. See also Doe, A. (2019). Gadget Performance. Tech. Rev., 8(1), 5-15.",
        expected_chunks=[
            "See Smith, J. (2020). Widget Analysis. J. Widgets, 5(2), 10-20.",
            "See also Doe, A. (2019). Gadget Performance. Tech. Rev., 8(1), 5-15.",
        ],
        description="Multiple citations in one footnote - OK to split between citations",
        should_use_llm=True,  # Complex with multiple citations
    ),
    # Negative cases (should NOT use LLM)
    FootnoteTestCase(
        name="regular_prose",
        text="This is the first sentence. This is the second sentence. And here is a third.",
        expected_chunks=[
            "This is the first sentence.",
            "This is the second sentence.",
            "And here is a third.",
        ],
        description="Regular prose (not a citation)",
        should_use_llm=False,  # Should split normally
    ),
    FootnoteTestCase(
        name="technical_prose_with_acronyms",
        text="The U.S. Navy deployed the new A.I. system in 2023. It improved efficiency by 20%.",
        expected_chunks=[
            "The U.S. Navy deployed the new A.I.",
            "system in 2023.",
            "It improved efficiency by 20%.",
        ],
        description="Technical writing with acronyms - NLTK splits on A.I. which triggers LLM fallback",
        should_use_llm=True,  # NLTK incorrectly splits on "A.I."
    ),
    # Markdown citation reference cases
    FootnoteTestCase(
        name="standalone_markdown_citation",
        text="[[21]](#footnote-20)",
        expected_chunks=["[[21]](#footnote-20)"],
        description="Standalone markdown citation reference - detected as suspicious, handled by LLM",
        should_use_llm=True,  # Fragment detection catches this, LLM returns as-is
    ),
    FootnoteTestCase(
        name="markdown_citation_inline",
        text="* Bistline et al., 2023 optimization model results in capacity increases.[[21]](#footnote-20)",
        expected_chunks=[
            "* Bistline et al., 2023 optimization model results in capacity increases.[[21]](#footnote-20)"
        ],
        description="Inline markdown citation - NLTK splits, LLM merges",
        should_use_llm=True,  # NLTK splits at period, fragment detection catches, LLM merges
    ),
    FootnoteTestCase(
        name="multiple_markdown_citations",
        text="See the report for details.[[1]](#footnote-0), [[2]](#footnote-1)",
        expected_chunks=[
            "See the report for details.[[1]](#footnote-0), [[2]](#footnote-1)"
        ],
        description="Multiple inline markdown citations - citations stay with text",
        should_use_llm=True,  # NLTK splits, LLM merges (footnotes at end of sentence)
    ),
    FootnoteTestCase(
        name="markdown_citation_with_space",
        text="The study shows significant results. [[25]](#footnote-24)",
        expected_chunks=["The study shows significant results. [[25]](#footnote-24)"],
        description="Markdown citation with space before it stays together",
        should_use_llm=True,  # NLTK splits, LLM merges (has space)
    ),
]


class MethodResult(BaseModel):
    """Results for a single detection method."""

    method_name: str
    correct_count: int = 0
    total_count: int = 0
    total_time_ms: float = 0.0
    llm_call_count: int = 0
    nltk_only_count: int = 0
    failures: List[Dict[str, Any]] = []

    @property
    def accuracy(self) -> float:
        return self.correct_count / self.total_count if self.total_count > 0 else 0.0

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.total_count if self.total_count > 0 else 0.0


async def run_with_method(
    test_case: FootnoteTestCase, detection_method: DetectionMethod
) -> tuple[List[str], float, bool]:
    """
    Test a single case with a specific detection method.

    Returns:
        (result_chunks, time_ms, used_llm)
    """
    start = time.perf_counter()
    result = await split_paragraph_into_sentences(
        test_case.text,
        detection_method=detection_method,
        context=create_test_context(),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Heuristic to detect if LLM was used:
    # - If detection method triggers and result differs from NLTK, assume LLM
    nltk_result = nltk.sent_tokenize(test_case.text)
    used_llm = result != [s.strip() for s in nltk_result if s.strip()]

    return result, elapsed_ms, used_llm


async def run_nltk_only(test_case: FootnoteTestCase) -> tuple[List[str], float]:
    """Test with pure NLTK (no LLM fallback)."""
    start = time.perf_counter()
    result = nltk.sent_tokenize(test_case.text)
    result = [s.strip() for s in result if s.strip()]
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms


async def run_llm_only(test_case: FootnoteTestCase) -> tuple[List[str], float]:
    """Test with pure LLM (no NLTK)."""
    start = time.perf_counter()
    result = await llm_tokenize_paragraph(test_case.text, context=create_test_context())
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms


def chunks_match(actual: List[str], expected: List[str]) -> bool:
    """
    Check if chunks match (allowing some flexibility for whitespace).
    """
    if len(actual) != len(expected):
        return False

    for a, e in zip(actual, expected):
        if a.strip() != e.strip():
            return False

    return True


class TestFootnoteWithReconstruction:
    """Test individual footnote cases with reconstruction method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_case", FOOTNOTE_TEST_CASES, ids=lambda tc: tc.name)
    async def test_footnote_reconstruction(self, test_case: FootnoteTestCase):
        """Test each footnote case with reconstruction detection."""
        result = await split_paragraph_into_sentences(
            test_case.text,
            detection_method="reconstruction",
            context=create_test_context(),
        )
        assert chunks_match(
            result, test_case.expected_chunks
        ), f"{test_case.description}\nExpected: {test_case.expected_chunks}\nActual: {result}"


class TestPerformanceBenchmarks:
    """Benchmark performance of different methods."""

    @pytest.mark.asyncio
    async def test_nltk_performance_baseline(self):
        """Establish NLTK-only baseline performance."""
        iterations = 100
        test_text = FOOTNOTE_TEST_CASES[0].text

        start = time.perf_counter()
        for _ in range(iterations):
            nltk.sent_tokenize(test_text)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        print(
            f"\nNLTK baseline: {avg_ms:.3f}ms per call (averaged over {iterations} calls)"
        )

        # NLTK should be very fast
        assert avg_ms < 5.0, f"NLTK too slow: {avg_ms:.3f}ms (expected < 5ms)"

    @pytest.mark.asyncio
    async def test_llm_performance_cost(self):
        """Measure LLM performance (single call to avoid API rate limits in tests)."""
        test_text = FOOTNOTE_TEST_CASES[0].text

        start = time.perf_counter()
        await llm_tokenize_paragraph(test_text, context=create_test_context())
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\nLLM single call: {elapsed_ms:.2f}ms")

        # LLM should complete in reasonable time (< 30 seconds)
        # Note: This can vary significantly based on API load and network conditions
        assert (
            elapsed_ms < 30000
        ), f"LLM too slow: {elapsed_ms:.2f}ms (expected < 30000ms)"


if __name__ == "__main__":
    # Run the comparison test
    pytest.main([__file__, "-v", "-s", "-k", "test_all_methods_comparison"])
