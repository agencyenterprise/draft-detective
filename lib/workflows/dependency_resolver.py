"""
Automatic dependency resolution for workflows.

Resolves all required transitive dependencies and returns workflows
in dependency order (dependencies before dependents).
"""

import logging
from graphlib import TopologicalSorter
from typing import List, Set

from lib.workflows.models import WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)


def resolve_workflow_dependencies(
    workflow_types: List[WorkflowRunType],
) -> List[WorkflowRunType]:
    """
    Resolve all required transitive dependencies for given workflows.

    Returns workflows in dependency order (dependencies run first).

    Example:
        Input: [REFERENCE_VALIDATION]
        Output: [DOCUMENT_PROCESSING, REFERENCE_EXTRACTION, REFERENCE_VALIDATION]

    Args:
        workflow_types: List of workflow types requested by user

    Returns:
        Complete list of workflows including dependencies, in execution order

    Raises:
        ValueError: If circular dependencies are detected
    """
    if not workflow_types:
        return []

    # Step 1: We need to collect all required dependencies (transitive) because some workflows are dependencies of other workflows.
    all_workflows = _collect_all_dependencies(workflow_types)

    # Step 2: We need to sort in dependency order (dependencies first) because we need to run dependencies first.
    sorted_workflows = _topological_sort(all_workflows)

    logger.info(
        f"Resolved {len(workflow_types)} workflows to {len(sorted_workflows)}: "
        f"{[w.value for w in sorted_workflows]}"
    )

    return sorted_workflows


def _collect_all_dependencies(
    workflow_types: List[WorkflowRunType],
) -> Set[WorkflowRunType]:
    """
    Collect all required transitive dependencies.

    Uses depth-first search to traverse the dependency graph.
    """
    all_workflows: Set[WorkflowRunType] = set()
    visiting: Set[WorkflowRunType] = set()  # We need for cycle detection

    def visit(workflow_type: WorkflowRunType):
        """Visit a workflow and its dependencies."""
        if workflow_type in visiting:
            raise ValueError(
                f"Circular dependency detected involving {workflow_type.value}"
            )

        if workflow_type in all_workflows:
            return  # Already fully processed

        visiting.add(workflow_type)
        all_workflows.add(workflow_type)

        manifest = get_workflow_manifest(workflow_type)
        for dep in manifest.required_dependencies:
            visit(dep)

        visiting.remove(workflow_type)

    for wf_type in workflow_types:
        visit(wf_type)

    return all_workflows


def _topological_sort(workflows: Set[WorkflowRunType]) -> List[WorkflowRunType]:
    """
    Sort workflows in dependency order using topological sort.

    Dependencies appear before their dependents in the result.

    Uses Python's graphlib.TopologicalSorter for standard topological sorting.
    """
    graph = {}
    for workflow_type in workflows:
        manifest = get_workflow_manifest(workflow_type)

        deps = {dep for dep in manifest.required_dependencies if dep in workflows}
        graph[workflow_type] = deps

    sorter = TopologicalSorter(graph)
    return list(sorter.static_order())
