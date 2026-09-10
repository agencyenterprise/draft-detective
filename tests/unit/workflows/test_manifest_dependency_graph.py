"""The manifests' dependency graph must be acyclic, optional edges included.

``wait_for_dependencies`` blocks on both required and optional dependencies
while they are pending, and a concurrent batch creates every run record as
PENDING before any of them starts. A cycle anywhere in that graph therefore
deadlocks the whole batch until the dependency timeout. The resolver only
validates required edges, so this test covers the full graph.
"""

from graphlib import CycleError, TopologicalSorter

import pytest

from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_all_manifests


def _full_graph() -> dict[WorkflowRunType, set[WorkflowRunType]]:
    return {
        wf_type: set(manifest.required_dependencies)
        | set(manifest.optional_dependencies)
        for wf_type, manifest in get_all_manifests().items()
    }


def test_dependency_graph_with_optional_edges_is_acyclic():
    graph = _full_graph()
    try:
        list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        cycle = " -> ".join(node.value for node in exc.args[1])
        pytest.fail(
            f"Workflow dependency cycle (required + optional edges): {cycle}. "
            "A pending run in this loop would block the others forever."
        )


def test_every_dependency_points_at_a_registered_workflow():
    registered = set(get_all_manifests())
    for wf_type, deps in _full_graph().items():
        unknown = deps - registered
        assert not unknown, f"{wf_type.value} depends on unregistered {unknown}"


def test_no_workflow_depends_on_itself():
    for wf_type, deps in _full_graph().items():
        assert wf_type not in deps, f"{wf_type.value} lists itself as a dependency"


def test_document_processing_does_not_wait_on_the_downloader():
    """Regression guard for the cycle document_processing -> reference_downloader
    -> reference_extraction -> document_processing. The downloader caches the
    markdown of the files it saves, so document processing has no reason to
    wait for it."""
    manifest = get_all_manifests()[WorkflowRunType.DOCUMENT_PROCESSING]
    assert WorkflowRunType.REFERENCE_DOWNLOADER not in manifest.optional_dependencies
    assert WorkflowRunType.REFERENCE_DOWNLOADER not in manifest.required_dependencies
