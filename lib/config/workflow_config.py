"""Workflow configuration loader.

Loads organization-specific prompts and rules from YAML.
Supports external configuration via WORKFLOW_CONFIG_PATH environment variable.
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar

import yaml

T = TypeVar("T")
logger = logging.getLogger(__name__)


def _get_config_path() -> Path:
    """Get the workflow configuration file path.

    Priority:
    1. WORKFLOW_CONFIG_PATH environment variable (external file)
    2. Default bundled config (workflow_config.yaml in this directory)

    Returns:
        Path to the configuration file

    Raises:
        FileNotFoundError: If the external config path is set but file doesn't exist
    """
    external_path = os.getenv("WORKFLOW_CONFIG_PATH")

    if external_path:
        config_path = Path(external_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"Workflow config not found at WORKFLOW_CONFIG_PATH: {external_path}"
            )
        logger.info(f"Loading workflow config from external path: {external_path}")
        return config_path

    return Path(__file__).parent / "workflow_config.yaml"


@lru_cache(maxsize=1)
def _load_config() -> Dict[str, Any]:
    """Load and cache the workflow configuration."""
    config_path = _get_config_path()
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def invalidate_config_cache() -> None:
    """Invalidate the config cache to reload from disk.

    Call this if the configuration file has been updated and you want
    to reload it without restarting the application.
    """
    _load_config.cache_clear()
    logger.info("Workflow config cache invalidated")


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
        get_workflow_config("about_this", "boilerplate")  # Returns string
        get_workflow_config("about_this", "requirements")  # Returns dict
        get_workflow_config("about_authors", "rules")  # Returns dict
    """
    config = _load_config()
    workflow = config.get("workflows", {}).get(workflow_type, {})

    if key is None:
        return workflow

    return workflow.get(key, default if default is not None else {})
