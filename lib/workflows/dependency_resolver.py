"""
Automatic dependency resolution for workflows.

Resolves all required transitive dependencies and returns workflows
in dependency order (dependencies before dependents).
"""

import logging
from graphlib import TopologicalSorter
from typing import Dict, List, Optional, Set

from lib.workflows.models import ClaimExtractionVersion, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# When claim_extraction_version is V1, substitute V2 dependencies with V1
_V1_SUBSTITUTIONS: Dict[WorkflowRunType, WorkflowRunType] = {
    WorkflowRunType.CLAIM_EXTRACTION_V2: WorkflowRunType.CLAIM_EXTRACTION,
}


def _build_substitution_map(
    claim_extraction_version: ClaimExtractionVersion,
) -> Dict[WorkflowRunType, WorkflowRunType]:
    """Build the dependency substitution map for the given version."""
    if claim_extraction_version == ClaimExtractionVersion.V1:
        return _V1_SUBSTITUTIONS
    return {}


def _apply_substitution(
    workflow_type: WorkflowRunType,
    substitutions: Dict[WorkflowRunType, WorkflowRunType],
) -> WorkflowRunType:
    """Apply substitution map to a single workflow type."""
    return substitutions.get(workflow_type, workflow_type)


def apply_dependency_substitutions(
    workflow_types: List[WorkflowRunType],
    claim_extraction_version: Optional[ClaimExtractionVersion] = None,
) -> List[WorkflowRunType]:
    """Apply version-specific substitutions to a list of workflow types."""
    if not claim_extraction_version:
        return workflow_types

    substitutions = _build_substitution_map(claim_extraction_version)
    return [_apply_substitution(wf, substitutions) for wf in workflow_types]


def resolve_workflow_dependencies(
    workflow_types: List[WorkflowRunType],
    claim_extraction_version: Optional[ClaimExtractionVersion] = None,
) -> List[WorkflowRunType]:
    """
    Resolve all required transitive dependencies for given workflows.

    Returns workflows in dependency order (dependencies run first).

    When claim_extraction_version is provided, version-specific dependency
    substitutions are applied (e.g., CLAIM_EXTRACTION_V2 is replaced with
    CLAIM_EXTRACTION when version is V1).

    Example:
        Input: [REFERENCE_VALIDATION]
        Output: [DOCUMENT_PROCESSING, REFERENCE_EXTRACTION, REFERENCE_VALIDATION]

    Args:
        workflow_types: List of workflow types requested by user
        claim_extraction_version: Which claim extraction version to use.
            Defaults to None (no substitution, manifests used as-is).

    Returns:
        Complete list of workflows including dependencies, in execution order

    Raises:
        ValueError: If circular dependencies are detected
    """
    if not workflow_types:
        return []

    substitutions = (
        _build_substitution_map(claim_extraction_version)
        if claim_extraction_version
        else {}
    )

    # Step 1: We need to collect all required dependencies (transitive) because some workflows are dependencies of other workflows.
    all_workflows = _collect_all_dependencies(workflow_types, substitutions)

    # Step 2: We need to sort in dependency order (dependencies first) because we need to run dependencies first.
    sorted_workflows = _topological_sort(all_workflows, substitutions)

    logger.info(
        f"Resolved {len(workflow_types)} workflows to {len(sorted_workflows)}: "
        f"{[w.value for w in sorted_workflows]}"
    )

    return sorted_workflows


def _collect_all_dependencies(
    workflow_types: List[WorkflowRunType],
    substitutions: Dict[WorkflowRunType, WorkflowRunType],
) -> Set[WorkflowRunType]:
    """
    Collect all required transitive dependencies.

    Uses depth-first search to traverse the dependency graph.
    Substitutions are applied to each dependency as it is encountered.
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
            resolved_dep = _apply_substitution(dep, substitutions)
            visit(resolved_dep)

        visiting.remove(workflow_type)

    for wf_type in workflow_types:
        resolved_wf = _apply_substitution(wf_type, substitutions)
        visit(resolved_wf)

    return all_workflows


def _topological_sort(
    workflows: Set[WorkflowRunType],
    substitutions: Dict[WorkflowRunType, WorkflowRunType],
) -> List[WorkflowRunType]:
    """
    Sort workflows in dependency order using topological sort.

    Dependencies appear before their dependents in the result.
    Substitutions are applied when reading manifest dependencies.

    Uses Python's graphlib.TopologicalSorter for standard topological sorting.
    """
    graph = {}
    for workflow_type in workflows:
        manifest = get_workflow_manifest(workflow_type)

        deps = {
            _apply_substitution(dep, substitutions)
            for dep in manifest.required_dependencies
            if _apply_substitution(dep, substitutions) in workflows
        }
        graph[workflow_type] = deps

    sorter = TopologicalSorter(graph)
    return list(sorter.static_order())
