"""Workflow configuration loader.

Loads organization-specific prompts and rules from YAML.
Will be replaced by database queries in the future.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, overload

import yaml

T = TypeVar("T")


@lru_cache(maxsize=1)
def _load_config() -> Dict[str, Any]:
    """Load and cache the workflow configuration."""
    config_path = Path(__file__).parent / "workflow_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_workflow_config(
    workflow_type: str,
    key: Optional[str] = None,
    default: Any = None,
) -> Any:
    """Get configuration for a workflow type.

    Args:
        workflow_type: The workflow type (e.g., 'about_this', 'about_authors')
        key: Optional config key within the workflow (e.g., 'requirements', 'rules')
        default: Default value if key not found

    Returns:
        Full workflow config if key is None, otherwise the specific key's value

    Examples:
        get_workflow_config("about_this")  # Returns full about_this config
        get_workflow_config("about_this", "tasp_boilerplate")  # Returns string
        get_workflow_config("about_this", "requirements")  # Returns dict
        get_workflow_config("about_authors", "rules")  # Returns dict
    """
    config = _load_config()
    workflow = config.get("workflows", {}).get(workflow_type, {})

    if key is None:
        return workflow

    return workflow.get(key, default if default is not None else {})
