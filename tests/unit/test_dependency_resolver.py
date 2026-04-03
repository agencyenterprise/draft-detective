"""Tests for automatic workflow dependency resolution."""

import pytest
from unittest.mock import MagicMock, patch

from lib.workflows.dependency_resolver import (
    get_required_dependents,
    resolve_workflow_dependencies,
)
from lib.workflows.models import WorkflowRunType


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

    assert WorkflowRunType.CLAIM_EXTRACTION in result
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


# ---------------------------------------------------------------------------
# get_required_dependents
# ---------------------------------------------------------------------------


def _make_all_manifests(deps: dict[WorkflowRunType, list[WorkflowRunType]]):
    """Build a fake all-manifests dict from a {type: required_deps} mapping."""
    manifests = {}
    for wf_type, required in deps.items():
        m = MagicMock()
        m.required_dependencies = required
        manifests[wf_type] = m
    return manifests


def _patch_all_manifests(manifests):
    return patch("lib.workflows.registry.get_all_manifests", return_value=manifests)


def test_get_required_dependents_returns_empty_for_leaf_node():
    """A workflow that no one depends on returns an empty list."""
    manifests = _make_all_manifests(
        {
            WorkflowRunType.DOCUMENT_PROCESSING: [],
            WorkflowRunType.REFERENCE_EXTRACTION: [WorkflowRunType.DOCUMENT_PROCESSING],
        }
    )
    with _patch_all_manifests(manifests):
        result = get_required_dependents(WorkflowRunType.REFERENCE_EXTRACTION)

    assert result == []


def test_get_required_dependents_returns_direct_dependents():
    """Direct dependents of a workflow are returned."""
    manifests = _make_all_manifests(
        {
            WorkflowRunType.DOCUMENT_PROCESSING: [],
            WorkflowRunType.REFERENCE_EXTRACTION: [WorkflowRunType.DOCUMENT_PROCESSING],
            WorkflowRunType.REFERENCE_VALIDATION: [WorkflowRunType.DOCUMENT_PROCESSING],
        }
    )
    with _patch_all_manifests(manifests):
        result = get_required_dependents(WorkflowRunType.DOCUMENT_PROCESSING)

    assert set(result) == {
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.REFERENCE_VALIDATION,
    }


def test_get_required_dependents_returns_transitive_dependents():
    """BFS finds indirect dependents (A requires B requires C → get_required_dependents(C) includes A)."""
    manifests = _make_all_manifests(
        {
            WorkflowRunType.DOCUMENT_PROCESSING: [],
            WorkflowRunType.REFERENCE_EXTRACTION: [WorkflowRunType.DOCUMENT_PROCESSING],
            WorkflowRunType.REFERENCE_VALIDATION: [WorkflowRunType.REFERENCE_EXTRACTION],
        }
    )
    with _patch_all_manifests(manifests):
        result = get_required_dependents(WorkflowRunType.DOCUMENT_PROCESSING)

    assert set(result) == {
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.REFERENCE_VALIDATION,
    }


def test_get_required_dependents_does_not_include_source_workflow():
    """The queried workflow type itself is never in the result."""
    manifests = _make_all_manifests(
        {
            WorkflowRunType.DOCUMENT_PROCESSING: [],
            WorkflowRunType.REFERENCE_EXTRACTION: [WorkflowRunType.DOCUMENT_PROCESSING],
        }
    )
    with _patch_all_manifests(manifests):
        result = get_required_dependents(WorkflowRunType.DOCUMENT_PROCESSING)

    assert WorkflowRunType.DOCUMENT_PROCESSING not in result


def test_get_required_dependents_no_duplicates_in_diamond_graph():
    """A workflow reached through multiple paths is returned only once."""
    # DOCUMENT_PROCESSING is required by both REFERENCE_EXTRACTION and CHUNK_SPLITTING.
    # REFERENCE_VALIDATION requires REFERENCE_EXTRACTION.
    # Cancelling DOCUMENT_PROCESSING should list both paths without duplicates.
    manifests = _make_all_manifests(
        {
            WorkflowRunType.DOCUMENT_PROCESSING: [],
            WorkflowRunType.REFERENCE_EXTRACTION: [WorkflowRunType.DOCUMENT_PROCESSING],
            WorkflowRunType.CHUNK_SPLITTING: [WorkflowRunType.DOCUMENT_PROCESSING],
            WorkflowRunType.REFERENCE_VALIDATION: [WorkflowRunType.REFERENCE_EXTRACTION],
        }
    )
    with _patch_all_manifests(manifests):
        result = get_required_dependents(WorkflowRunType.DOCUMENT_PROCESSING)

    assert len(result) == len(set(result)), "No duplicates expected"
    assert set(result) == {
        WorkflowRunType.REFERENCE_EXTRACTION,
        WorkflowRunType.CHUNK_SPLITTING,
        WorkflowRunType.REFERENCE_VALIDATION,
    }
