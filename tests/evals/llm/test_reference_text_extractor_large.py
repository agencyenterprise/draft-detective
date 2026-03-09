from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import pytest
import yaml
from pydantic import BaseModel, Field

from lib.agents.reference_text_extractor_v2 import (
    ReferenceExtractorV2Agent,
)
from lib.config.langfuse import langfuse_handler
from lib.services.file import FileDocument
from lib.services.file_artifacts_service.mock import MockFileArtifactsService
from tests.conftest import create_test_context

TESTS_DIR = Path(__file__).parent.parent

# Configurable thresholds for fuzzy matching
SIMILARITY_THRESHOLD = 0.85  # Min similarity to consider a match
OVERALL_PASS_THRESHOLD = 0.95  # Min % of references that must match


class ReferenceMatchResult(BaseModel):
    """Result of matching a single expected reference to actual output."""

    expected: Optional[str] = Field(description="Expected reference text")
    actual: Optional[str] = Field(description="Best matching actual reference")
    similarity: float = Field(description="Similarity score (0.0-1.0)")
    passed: bool = Field(description="Whether this reference matched successfully")


class ComparisonResult(BaseModel):
    """Overall result of comparing expected vs actual references."""

    matches: list[ReferenceMatchResult] = Field(description="Per-reference results")
    match_rate: float = Field(description="Percentage of successful matches")
    total_expected: int = Field(description="Number of expected references")
    total_actual: int = Field(description="Number of actual references")
    matched_count: int = Field(description="Number of successfully matched references")
    missing_count: int = Field(description="Expected references not found in actual")
    extra_count: int = Field(description="Actual references not in expected")


def compare_references_relaxed(
    expected: list[str],
    actual: list[str],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> ComparisonResult:
    """Compare references with fuzzy matching and per-item reporting.

    Uses SequenceMatcher to find the best match for each expected reference
    in the actual output. Allows for minor string differences while still
    detecting missing or extra references.

    Args:
        expected: List of expected reference strings
        actual: List of actual reference strings from the model
        similarity_threshold: Minimum similarity score to consider a match

    Returns:
        ComparisonResult with per-reference details and overall metrics
    """
    matches: list[ReferenceMatchResult] = []
    actual_copy = list(actual)

    for exp_ref in expected:
        best_match: Optional[str] = None
        best_score = 0.0
        best_idx = -1

        for i, act_ref in enumerate(actual_copy):
            score = SequenceMatcher(None, exp_ref, act_ref).ratio()
            if score > best_score:
                best_score = score
                best_match = act_ref
                best_idx = i

        passed = best_score >= similarity_threshold and best_idx >= 0
        if passed:
            actual_copy.pop(best_idx)

        matches.append(
            ReferenceMatchResult(
                expected=exp_ref,
                actual=best_match if passed else None,
                similarity=best_score,
                passed=passed,
            )
        )

    # Track extra references in actual (not matched to any expected)
    for extra in actual_copy:
        matches.append(
            ReferenceMatchResult(
                expected=None,
                actual=extra,
                similarity=0.0,
                passed=False,
            )
        )

    matched_count = sum(1 for m in matches if m.passed)
    total = len(matches) if matches else 1

    return ComparisonResult(
        matches=matches,
        match_rate=matched_count / total,
        total_expected=len(expected),
        total_actual=len(actual),
        matched_count=matched_count,
        missing_count=sum(1 for m in matches if m.expected and not m.passed),
        extra_count=sum(1 for m in matches if m.actual and not m.expected),
    )


def format_failure_report(result: ComparisonResult, max_examples: int = 10) -> str:
    """Format a human-readable failure report for debugging.

    Args:
        result: Comparison result with match details
        max_examples: Maximum number of failure examples to show

    Returns:
        Formatted string describing failures
    """
    lines = [
        f"Match rate: {result.match_rate:.1%} "
        f"({result.matched_count}/{result.total_expected} expected matched)",
        f"Missing: {result.missing_count}, Extra: {result.extra_count}",
        f"Total expected: {result.total_expected}, Total actual: {result.total_actual}",
        "",
    ]

    failures = [m for m in result.matches if not m.passed]

    if failures:
        lines.append(f"First {min(len(failures), max_examples)} failures:")
        lines.append("-" * 60)

        for i, f in enumerate(failures[:max_examples]):
            if f.expected and not f.actual:
                lines.append(f"[{i+1}] MISSING (best sim={f.similarity:.3f}):")
                lines.append(f"    Expected: {f.expected}")
            elif f.actual and not f.expected:
                lines.append(f"[{i+1}] EXTRA:")
                lines.append(f"    Actual: {f.actual}")
            else:
                lines.append(f"[{i+1}] LOW SIMILARITY ({f.similarity:.3f}):")
                lines.append(f"    Expected: {f.expected}")
                lines.append(f"    Actual:   {f.actual if f.actual else 'None'}")
            lines.append("")

        remaining = len(failures) - max_examples
        if remaining > 0:
            lines.append(f"... and {remaining} more failures")

    return "\n".join(lines)


def _load_stress_test_yaml(yaml_filename: str) -> tuple[str, list[str]]:
    """Load a stress test YAML file and return document content and expected references."""
    data_dir = TESTS_DIR / "data" / "reference_extraction_stress_test"
    yaml_path = data_dir / yaml_filename

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    document_name = data["document"]
    document_path = data_dir / document_name

    with open(document_path, "r", encoding="utf-8") as f:
        document_content = f.read()

    return document_content, data["references"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "yaml_filename,case_name",
    [
        ("expected_RAND_RRA4036-1.yaml", "RAND_RRA4036-1"),
        ("expected_RAND_RRA4636-1.yaml", "RAND_RRA4636-1"),
    ],
    ids=["RAND_RRA4036-1", "RAND_RRA4636-1"],
)
async def test_reference_text_extractor_large(
    yaml_filename: str, case_name: str, test_models
):
    """Test reference text extraction from large documents."""
    document_content, expected_references = _load_stress_test_yaml(yaml_filename)

    file_artifacts_service = MockFileArtifactsService(
        main_file=FileDocument(
            markdown=document_content,
            file_name="document.md",
            file_path="document.md",
            file_type="text/markdown",
            markdown_token_count=len(document_content),
            file_id="stress_test_file_id",
        )
    )

    agent = ReferenceExtractorV2Agent(create_test_context(file_artifacts_service))
    result = await agent.ainvoke(
        prompt_kwargs={},
        config={
            "run_name": f"test::reference_extractor::{case_name}",
            "callbacks": [langfuse_handler],
        },
    )

    # Extract text from ExtractedReferenceWithLines objects for comparison
    actual_references = [ref.text for ref in result.references]

    comparison = compare_references_relaxed(
        expected_references,
        actual_references,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )

    assert (
        comparison.match_rate >= OVERALL_PASS_THRESHOLD
    ), f"{case_name} failed:\n{format_failure_report(comparison)}"
