"""Utility functions for field comparison operations."""

import json
from typing import Any


def serialize_value(value: Any) -> str:
    """Serialize a value to string for storage in ComparisonExample.

    Args:
        value: Value to serialize

    Returns:
        Serialized string representation
    """
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float):
        return json.dumps(value)

    # For complex objects, try JSON first, fall back to str
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def to_dict(item: Any) -> dict:
    """Convert item to dict if needed.

    Args:
        item: Item to convert

    Returns:
        Dictionary representation of the item
    """
    if isinstance(item, dict):
        return item
    elif hasattr(item, "model_dump"):
        return item.model_dump()
    elif hasattr(item, "__dict__"):
        return item.__dict__
    else:
        return {"value": item}


def build_rationale(
    field_path: str, passed: bool, total: int, passed_count: int
) -> str:
    """Build human-readable rationale.

    Args:
        field_path: Dot-separated field path
        passed: Whether all instances passed
        total: Total number of instances
        passed_count: Number of instances that passed

    Returns:
        Human-readable rationale string
    """
    if passed:
        return f"All {total} instance(s) of '{field_path}' matched"
    else:
        failed_count = total - passed_count
        return f"{failed_count}/{total} instance(s) of '{field_path}' failed"
