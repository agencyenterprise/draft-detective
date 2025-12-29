import logging
from typing import List, Optional

from lib.workflows.claim_substantiation.state import ClaimSubstantiatorState
from lib.workflows.base import DocumentIssue, WorkflowRunType
from lib.workflows.registry import get_workflow_manifest
from lib.workflows.types import WorkflowState

logger = logging.getLogger(__name__)


def convert_to_issues(results: List[WorkflowState]) -> List[DocumentIssue]:
    """Convert workflow results to issues, dispatching to appropriate converter for each state type."""
    all_issues: List[DocumentIssue] = []

    # Find ClaimSubstantiatorState to pass to reference validation converter
    claim_state: Optional[ClaimSubstantiatorState] = None
    for result in results:
        if result.type == WorkflowRunType.CLAIM_SUBSTANTIATION:
            claim_state = result
            break

    for result in results:
        try:
            issues = _convert_state_to_issues(result, claim_state)
            all_issues.extend(issues)
        except Exception as e:
            logger.error(f"Error converting state to issues: {e}", exc_info=True)
            continue

    # Sort all issues by severity
    all_issues.sort(key=lambda x: x.severity.sort_index(), reverse=True)

    return all_issues


def _convert_state_to_issues(
    state: WorkflowState,
    claim_state: Optional[ClaimSubstantiatorState] = None,
) -> List[DocumentIssue]:
    """Dispatch to the appropriate converter based on state type using the registry."""
    try:
        manifest = get_workflow_manifest(state.type)
        return manifest.convert_state_to_issues(state, claim_state)
    except Exception as e:
        logger.error(f"Error converting state to issues: {e}", exc_info=True)
        return []
