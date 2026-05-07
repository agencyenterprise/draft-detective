from typing import Any, List

from langchain_core.messages import BaseMessage

from lib.services.workflow_cost.breakdown import UsageRecord


def _get_attr_or_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _resolve_model_name(message: Any) -> str | None:
    """Read model name from response_metadata. Returns None if not found."""
    response_metadata = _get_attr_or_key(message, "response_metadata") or {}
    if not isinstance(response_metadata, dict):
        return None
    # Anthropic uses "model_name", OpenAI uses "model"
    return response_metadata.get("model_name") or response_metadata.get("model")


def _extract_record(message: Any) -> UsageRecord | None:
    """Build a UsageRecord from a single message, or return None if no usage data."""
    usage_metadata = _get_attr_or_key(message, "usage_metadata")
    if not usage_metadata or not isinstance(usage_metadata, dict):
        return None

    model_name = _resolve_model_name(message)
    if not model_name:
        return None

    input_details = usage_metadata.get("input_token_details") or {}
    cache_read = int(input_details.get("cache_read", 0) or 0)

    # On Anthropic, usage_metadata.input_tokens includes cache_read + cache_creation.
    # Subtract cache_read so it's priced at the cached rate; any cache_creation tokens
    # remain in input_tokens and are priced as regular input.
    raw_input = int(usage_metadata.get("input_tokens", 0) or 0)
    input_tokens = max(raw_input - cache_read, 0)
    output_tokens = int(usage_metadata.get("output_tokens", 0) or 0)

    return UsageRecord(
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
    )


def walk_state_for_usage(state: Any) -> List[UsageRecord]:
    """Recursively walk a workflow state and collect token usage from all messages.

    Handles:
    - Live BaseMessage instances (during runtime)
    - Serialized message dicts (loaded from checkpointer)
    - Messages nested anywhere: top-level lists, dicts, Pydantic models
    """
    records: List[UsageRecord] = []
    _walk(state, records, _seen=set())
    return records


def _walk(node: Any, records: List[UsageRecord], _seen: set) -> None:
    if node is None or isinstance(node, (str, int, float, bool, bytes)):
        return

    obj_id = id(node)
    if obj_id in _seen:
        return
    _seen.add(obj_id)

    # Live BaseMessage
    if isinstance(node, BaseMessage):
        record = _extract_record(node)
        if record is not None:
            records.append(record)
        return

    # Serialized message dict (has usage_metadata key)
    if isinstance(node, dict) and "usage_metadata" in node:
        record = _extract_record(node)
        if record is not None:
            records.append(record)
        # Don't return — keep walking in case there are nested message lists too

    if isinstance(node, dict):
        for value in node.values():
            _walk(value, records, _seen)
        return

    if isinstance(node, (list, tuple, set)):
        for item in node:
            _walk(item, records, _seen)
        return

    # Pydantic model — iterate field values directly (preserves BaseMessage instances)
    node_type = type(node)
    if hasattr(node_type, "model_fields"):
        for field_name in node_type.model_fields:
            _walk(getattr(node, field_name, None), records, _seen)
        return

    if hasattr(node, "__dict__"):
        _walk(vars(node), records, _seen)
