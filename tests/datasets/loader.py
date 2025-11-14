"""Utility module for loading and parsing test datasets from YAML files."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field


class TestConfig(BaseModel):
    """Model for test evaluation configuration."""

    strict_fields: Optional[Union[set, dict]] = Field(default_factory=set)
    llm_fields: Optional[Union[set, dict]] = Field(default_factory=set)
    ignore_fields: Optional[Union[set, dict]] = Field(default_factory=set)
    llm_instructions: Optional[str] = Field(
        default=None,
        description="Special instructions to include in the LLM-as-a-judge prompt for semantic comparison",
    )


class DatasetItem(BaseModel):
    """Model for a single test case."""

    name: str
    description: str
    input: Dict[str, Any]
    expected_output: Dict[str, Any]


class Dataset(BaseModel):
    """Model for the complete dataset."""

    name: str
    description: str
    items: List[DatasetItem]
    test_config: Optional[TestConfig] = None


def load_dataset(dataset_path: str) -> Dataset:
    """Load a dataset from a YAML file.

    Args:
        dataset_path: Path to the YAML dataset file

    Returns:
        Parsed Dataset object

    Raises:
        FileNotFoundError: If the dataset file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
        ValidationError: If the dataset doesn't match the expected schema
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Dataset(**data["dataset"])
