from typing import List

from lib.workflows.models import WorkflowRunType
from lib.workflows.types import WorkflowState


def get_state_by_type(
    type: WorkflowRunType, states: List[WorkflowState]
) -> WorkflowState | None:
    """
    Get a state by type from a list of states.
    """

    for state in states:
        if state.type == type:
            return state
    return None


def get_state_by_type_or_raise(
    type: WorkflowRunType, states: List[WorkflowState]
) -> WorkflowState:
    """
    Get a state by type from a list of states, or raise an error if it's not found.
    """

    state = get_state_by_type(type, states)

    if state is None:
        raise ValueError(f"State of type {type} not found in states")

    return state
