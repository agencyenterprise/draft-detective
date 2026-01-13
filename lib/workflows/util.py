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


def get_main_file_id(all_states: List[WorkflowState]) -> str:
    """
    Get the ID of the main file from a list of states.
    """

    for state in all_states:
        if state.type == WorkflowRunType.DOCUMENT_PROCESSING:
            return state.file.file_id
    raise ValueError("No main file found in states")


def get_supporting_file_ids(all_states: List[WorkflowState]) -> List[str]:
    """
    Get the IDs of the supporting files from a list of states.
    """

    for state in all_states:
        if state.type == WorkflowRunType.DOCUMENT_PROCESSING:
            return [file.file_id for file in state.supporting_files or []]
    raise ValueError("No supporting files found in states")
