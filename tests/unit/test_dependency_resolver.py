"""Tests for automatic workflow dependency resolution."""

import pytest
from unittest.mock import patch

from lib.workflows.dependency_resolver import resolve_workflow_dependencies
from lib.workflows.models import ClaimExtractionVersion, WorkflowRunType


# Test helpers
def assert_order(result, *workflows):
    """Assert workflows appear in given order."""
    indices = [result.index(wf) for wf in workflows]
    assert indices == sorted(indices), f"Expected order {workflows}"


# Core functionality tests
def test_empty_and_simple_cases():
    """Test edge cases: empty list and workflow with no dependencies."""
    assert resolve_workflow_dependencies([]) == []
    assert resolve_workflow_dependencies([WorkflowRunType.DOCUMENT_PROCESSING]) == [
        WorkflowRunType.DOCUMENT_PROCESSING
    ]


def test_transitive_dependencies():
    """Test that all transitive dependencies are resolved in correct order."""
    # REFERENCE_VALIDATION -> REFERENCE_EXTRACTION -> DOCUMENT_PROCESSING
    result = resolve_workflow_dependencies([WorkflowRunType.REFERENCE_VALIDATION])

    assert set(result) == {
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.REFERENCE_VALIDATION,
    }
    assert_order(
        result,
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.REFERENCE_VALIDATION,
    )


def test_shared_dependencies():
    """Test that shared dependencies are not duplicated."""
    # REFERENCE_VALIDATION and LITERATURE_REVIEW both depend on REFERENCE_EXTRACTION
    result = resolve_workflow_dependencies(
        [WorkflowRunType.REFERENCE_VALIDATION, WorkflowRunType.LITERATURE_REVIEW]
    )

    # No duplicates
    assert len(result) == len(set(result))
    assert result.count(WorkflowRunType.REFERENCE_EXTRACTION) == 1
    assert result.count(WorkflowRunType.DOCUMENT_PROCESSING) == 1

    # Shared dependencies come first
    assert_order(
        result,
        WorkflowRunType.DOCUMENT_PROCESSING,
        WorkflowRunType.REFERENCE_EXTRACTION,
    )


def test_optional_dependencies_excluded():
    """Test that optional dependencies are NOT automatically included."""
    # CITATION_SUGGESTER optionally depends on LITERATURE_REVIEW
    result = resolve_workflow_dependencies([WorkflowRunType.CITATION_SUGGESTER])

    assert WorkflowRunType.CLAIM_EXTRACTION_V2 in result
    assert WorkflowRunType.LITERATURE_REVIEW not in result


def test_deterministic_ordering():
    """Test that resolution is deterministic across multiple runs."""
    workflows = [
        WorkflowRunType.REFERENCE_VALIDATION,
        WorkflowRunType.LITERATURE_REVIEW,
        WorkflowRunType.METHODOLOGICAL_ALIGNMENT,
    ]

    results = [resolve_workflow_dependencies(workflows) for _ in range(3)]
    assert all(r == results[0] for r in results[1:])


def test_circular_dependency_detection():
    """Test that circular dependencies are detected and raise an error."""
    from lib.workflows.registry import get_workflow_manifest

    original_get_manifest = get_workflow_manifest

    def mock_get_manifest(workflow_type):
        # Create artificial cycle: DOCUMENT_PROCESSING -> REFERENCE_EXTRACTION -> DOCUMENT_PROCESSING
        if workflow_type == WorkflowRunType.DOCUMENT_PROCESSING:

            class MockManifest:
                required_dependencies = [WorkflowRunType.REFERENCE_EXTRACTION]

            return MockManifest()
        return original_get_manifest(workflow_type)

    with patch(
        "lib.workflows.dependency_resolver.get_workflow_manifest", mock_get_manifest
    ):
        with pytest.raises(ValueError, match="Circular dependency detected"):
            resolve_workflow_dependencies([WorkflowRunType.DOCUMENT_PROCESSING])


# Version-aware substitution tests
def test_v1_substitutes_claim_extraction():
    """Test that V1 substitutes CLAIM_EXTRACTION_V2 with CLAIM_EXTRACTION."""
    result = resolve_workflow_dependencies(
        [WorkflowRunType.CLAIM_REFERENCE_VALIDATION],
        claim_extraction_version=ClaimExtractionVersion.V1,
    )

    assert WorkflowRunType.CLAIM_EXTRACTION in result
    assert WorkflowRunType.CLAIM_EXTRACTION_V2 not in result


def test_no_version_param_uses_manifests_as_is():
    """Test that omitting claim_extraction_version uses manifests without substitution."""
    result = resolve_workflow_dependencies(
        [WorkflowRunType.CITATION_SUGGESTER],
    )

    # Without version param, manifests are used as-is (they declare V2)
    assert WorkflowRunType.CLAIM_EXTRACTION_V2 in result
    assert WorkflowRunType.CLAIM_EXTRACTION not in result
