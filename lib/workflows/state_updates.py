from typing import Any, Mapping, TypeVar

from langgraph.channels.base import BaseChannel
from pydantic import BaseModel

StateT = TypeVar("StateT", bound=BaseModel)


def apply_node_update(
    state: StateT, update: Mapping[str, Any], channels: Mapping[str, BaseChannel]
) -> StateT:
    """Fold a single node's update into ``state`` exactly as LangGraph would.

    ``channels`` is the graph's ``StateGraph.channels``: the channel LangGraph
    derives from each state field (``BinaryOperatorAggregate`` for reducer
    fields, ``LastValue`` for plain ones). Seeding each channel with the current
    value and feeding it the update reuses LangGraph's own merge semantics,
    including ``Overwrite``. Keys without a channel are ignored.

    Used to surface partial results mid-superstep: LangGraph's ``"updates"``
    stream yields each parallel task's output as soon as it finishes, while the
    ``"values"`` stream only yields once the whole superstep is done.
    """
    merged: dict[str, Any] = {}
    for key, value in update.items():
        if key not in channels or key not in type(state).model_fields:
            continue
        channel = channels[key].from_checkpoint(getattr(state, key))
        channel.update([value])
        merged[key] = channel.get()
    return state.model_copy(update=merged)
