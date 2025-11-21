"""Shared test utilities for all agent tests.

This module provides reusable utilities that work across all agent test suites:
- Path resolution
- Document loading
- Supporting documents formatting
"""

import os
import uuid
import shutil
from enum import Enum
from pathlib import Path
from typing import Any
import json

import pytest
from pydantic import BaseModel
from xxhash import xxh128

from lib.config.env import config
from lib.services.file import create_file_document_from_path
from lib.models.agent_test_case import AgentTestCase


# Root tests directory
TESTS_DIR = Path(__file__).parent

# Whether to print per-field comparison details after each test
_PRINT_AGENT_FIELDS = False


# Store test case data during test execution
_agent_test_case_data = {}

# Environment variable key for sharing session_id across workers
_SESSION_ID_ENV_VAR = "PYTEST_LANGFUSE_SESSION_ID"

# Model comparison mode flag
_MODEL_COMPARISON_MODE = False


def pytest_addoption(parser):
    """Add CLI options for test diagnostics."""
    parser.addoption(
        "--print-agent-fields",
        action="store_true",
        default=False,
        help="Print detailed per-field agent comparison results after each test",
    )
    parser.addoption(
        "--skip-compare-models",
        action="store_true",
        default=False,
        help="Disable model comparison mode (model comparison is enabled by default)",
    )
    parser.addoption(
        "--comparison-models",
        action="store",
        default=None,
        help="Comma-separated list of models to compare (e.g., 'gpt-5,gpt-5-mini,gpt-4.1')",
    )


def pytest_configure(config):
    """Generate and set a single session ID for the entire test run.

    For pytest-xdist parallel execution, the controller process generates
    the session_id and shares it with workers via environment variable.
    """
    global _PRINT_AGENT_FIELDS, _MODEL_COMPARISON_MODE

    worker_id = os.environ.get("PYTEST_XDIST_WORKER")

    if worker_id:
        session_id = os.environ.get(_SESSION_ID_ENV_VAR)
        if not session_id:
            session_id = str(uuid.uuid4())
    else:
        session_id = str(uuid.uuid4())
        os.environ[_SESSION_ID_ENV_VAR] = session_id

    AgentTestCase.set_shared_session_id(session_id)

    # Enable printing via CLI flag or environment variable
    _PRINT_AGENT_FIELDS = bool(
        config.getoption("print_agent_fields") or os.getenv("AGENT_TEST_PRINT_FIELDS")
    )

    # Model comparison mode is enabled by default
    # Disable it only if --skip-compare-models flag is present or env var is set to skip
    skip_comparison = bool(
        config.getoption("skip_compare_models")
        or os.getenv("SKIP_MODEL_COMPARISON_MODE")
    )
    _MODEL_COMPARISON_MODE = not skip_comparison


def _extract_by_path(obj: Any, parts: list[str]) -> Any:
    """Extract nested values from dict/list given a field path split into parts.

    - If obj is a list, returns a list by mapping extraction over all items.
    - If obj is a dict, descends by key.
    - If obj or parts are empty, returns obj.
    """
    if obj is None or not parts:
        return obj
    head, *tail = parts
    if isinstance(obj, list):
        return [_extract_by_path(el, parts) for el in obj]
    if isinstance(obj, dict):
        return _extract_by_path(obj.get(head), tail)
    return None


def _serialize_for_xdist(obj):
    """Convert enums, sets, and Pydantic models to serializable types for pytest-xdist."""
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, BaseModel):
        return _serialize_for_xdist(obj.model_dump())
    elif isinstance(obj, dict):
        return {k: _serialize_for_xdist(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_xdist(item) for item in obj]
    else:
        return obj


def _serialize_field_comparisons(field_comparisons):
    """Serialize field comparisons to dicts."""
    return [
        fc.model_dump() if hasattr(fc, "model_dump") else fc for fc in field_comparisons
    ]


def _serialize_model_results(model_results):
    """Serialize model comparison results."""
    serialized = {}
    for model_name, result_data in model_results.items():
        serialized[model_name] = {
            "passed": result_data["passed"],
            "rationale": result_data["rationale"],
            "field_comparisons": _serialize_field_comparisons(
                result_data["field_comparisons"]
            ),
            "cost_usd": result_data.get("cost_usd", 0.0),
            "duration_seconds": result_data.get("duration_seconds", 0.0),
            "input_tokens": result_data.get("input_tokens", 0),
            "output_tokens": result_data.get("output_tokens", 0),
            "total_tokens": result_data.get("total_tokens", 0),
            "actual_output": result_data.get("actual_output", {}),
        }
    return serialized


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store AgentTestCase metadata during test execution."""
    outcome = yield
    report = outcome.get_result()

    # Only process the call phase (actual test execution)
    if call.when == "call":
        # Try to extract AgentTestCase from test parameters
        if hasattr(item, "callspec") and "case" in item.callspec.params:
            case = item.callspec.params["case"]

            if not case.model_results:
                return

            # Get baseline (first) model's result
            baseline_model = next(iter(case.model_results.keys()))
            baseline_result = case.model_results[baseline_model]

            # Build minimal test case data
            # Include actual_outputs for frontend backward compatibility
            baseline_actual_output = baseline_result.get("actual_output", {})

            agent_test_case_data = {
                "name": case.name,
                "agent": {"name": case.agent.name},
                "prompt_kwargs": {
                    k: (
                        v[:5000] + "... [Truncated]"
                        if isinstance(v, str) and len(v) > 5000
                        else v
                    )
                    for k, v in case.prompt_kwargs.items()
                },
                "expected_output": case.expected_dict,
                "actual_outputs": [baseline_actual_output],  # Frontend expects array
                "evaluation_config": {
                    "strict_fields": _serialize_for_xdist(case.strict_fields),
                    "llm_fields": _serialize_for_xdist(case.llm_fields),
                    "evaluator_model": case.evaluator_model,
                },
                "evaluation_result": {
                    "passed": baseline_result["passed"],
                    "rationale": baseline_result["rationale"],
                    "field_comparisons": _serialize_field_comparisons(
                        baseline_result["field_comparisons"]
                    ),
                },
                "session_id": getattr(case, "session_id", None),
            }

            # Include model comparison results if present
            if len(case.model_results) > 1:
                agent_test_case_data["model_comparison_results"] = (
                    _serialize_model_results(case.model_results)
                )

            report.agent_test_case_data = _serialize_for_xdist(agent_test_case_data)


@pytest.hookimpl()
def pytest_runtest_logreport(report):
    """Collect AgentTestCase data from worker processes into main process dict.

    This hook runs in the main process and receives reports from all workers,
    making it compatible with pytest-xdist parallel execution.
    """
    if hasattr(report, "agent_test_case_data"):
        _agent_test_case_data[report.nodeid] = report.agent_test_case_data

        # Optionally print per-field comparison details after the test
        if _PRINT_AGENT_FIELDS:
            _print_field_comparisons(report.agent_test_case_data)


def _print_field_comparisons(data):
    """Print detailed field comparison results for a test."""
    eval_result = data.get("evaluation_result", {})
    field_comparisons = eval_result.get("field_comparisons", [])

    if not field_comparisons:
        return

    print(f"\n=== Agent Field Comparisons: {data.get('name')} ===")
    print(f"Overall Result: {eval_result.get('rationale', 'No rationale')}\n")

    for fc in field_comparisons:
        status = "PASS" if fc.get("passed") else "FAIL"
        field_path = fc.get("field_path")
        comp_type = fc.get("comparison_type", "unknown")
        strategy = fc.get("matching_strategy")
        total = fc.get("total_instances")
        passed_count = fc.get("passed_instances")

        print(f"[{status}] {field_path}  ({comp_type})")
        print(f"  Matched: {passed_count}/{total}  Strategy: {strategy or 'N/A'}")
        print(f"  Rationale: {fc.get('rationale', 'No rationale')}")

        # Print expected/actual values
        expected_output = data.get("expected_output")
        actual_output = eval_result.get("actual_output")

        if expected_output and actual_output:
            parts = (field_path or "").split(".")
            expected_value = _extract_by_path(expected_output, parts)
            actual_value = _extract_by_path(actual_output, parts)

            print(f"  Expected: {_format_value(expected_value)}")
            print(f"  Actual:   {_format_value(actual_value)}")
        print()

    print("=== End Agent Field Comparisons ===\n")


def _format_value(value):
    """Format a value for display, handling JSON serialization."""
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


@pytest.hookimpl()
def pytest_json_modifyreport(json_report):
    """Modify the JSON report to include AgentTestCase metadata."""
    model_comparison_data = {}

    for test in json_report.get("tests", []):
        nodeid = test.get("nodeid")
        if nodeid in _agent_test_case_data:
            test_data = _agent_test_case_data[nodeid]
            test["agent_test_case"] = test_data

            if "model_comparison_results" in test_data:
                agent_name = test_data["agent"]["name"]
                test_name = test_data["name"]

                if agent_name not in model_comparison_data:
                    model_comparison_data[agent_name] = {}

                model_comparison_data[agent_name][test_name] = test_data[
                    "model_comparison_results"
                ]

    if model_comparison_data:
        json_report["model_comparison"] = model_comparison_data


def data_path(path: str) -> str:
    """
    Convert relative test data path to absolute path.

    Args:
        path: Relative path from tests/ directory (e.g., "data/common_knowledge/main.md")

    Returns:
        Absolute path to the file
    """
    return str(TESTS_DIR / path)


async def create_test_file_document_from_path(path: str):
    """
    Load a single document from test data.

    Copies the test file to the uploads directory with an xxhash-based filename,
    similar to how uploaded files are handled in production.

    Args:
        path: Relative path from tests/ directory

    Returns:
        FileDocument object with markdown content
    """
    source_path = data_path(path)

    # Read file content to generate hash
    with open(source_path, "rb") as f:
        content = f.read()

    # Generate xxhash similar to upload.py
    xxhash = xxh128(content).hexdigest()

    # Get file extension
    filename = os.path.basename(source_path)
    file_extension = os.path.splitext(filename)[1]

    # Construct destination path in uploads directory
    upload_dir = config.FILE_UPLOADS_MOUNT_PATH
    dest_path = os.path.join(upload_dir, xxhash + file_extension)

    # Copy file to uploads directory if it doesn't already exist
    if not os.path.exists(dest_path):
        os.makedirs(upload_dir, exist_ok=True)
        shutil.copy2(source_path, dest_path)

    # Use original filename for FileDocument
    original_file_name = filename

    return await create_file_document_from_path(
        dest_path, original_file_name=original_file_name, markdown_convert=True
    )


def extract_paragraph_from_chunk(full_document: str, chunk: str) -> str:
    """
    Extract paragraph context from chunk.

    For test purposes, we detect the paragraph that contains the chunk breaking the full document into paragraphs.

    In production, state.get_paragraph(chunk.paragraph_index) reconstructs
    the full paragraph from all chunks sharing the same paragraph_index.
    """

    paragraphs = full_document.split("\n")
    for paragraph in paragraphs:
        if chunk in paragraph:
            return paragraph

    raise ValueError(f"Chunk not found in full document: {chunk}")


def is_model_comparison_mode() -> bool:
    """Check if model comparison mode is enabled."""
    return _MODEL_COMPARISON_MODE


def get_comparison_models():
    """Get the list of models to compare in model comparison mode."""
    from lib.config.llm_models import (
        gpt_5_model,
        gpt_5_mini_model,
        gpt_5_1_model,
        gpt_4_1_model,
        claude_3_5_sonnet_model,
        gemini_2_flash_model,
    )

    # Default models to compare
    # Note: Agent's default model will be automatically added as baseline (position 0)
    return [
        gpt_5_model,
        gpt_5_mini_model,
        gpt_5_1_model,
        gpt_4_1_model,
        claude_3_5_sonnet_model,
        gemini_2_flash_model,
    ]


@pytest.fixture
def test_models():
    """Fixture providing models for test execution.

    Returns single model in normal mode, multiple models in comparison mode.
    """
    if is_model_comparison_mode():
        return get_comparison_models()
    # Return None to use agent's default model
    return None
