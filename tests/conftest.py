"""Shared test utilities for all agent tests.

This module provides reusable utilities that work across all agent test suites:
- Path resolution
- Document loading
- Supporting documents formatting
"""

import asyncio
import os
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional, Any
import json

import pytest
from pydantic import BaseModel

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


def pytest_addoption(parser):
    """Add CLI options for test diagnostics."""
    parser.addoption(
        "--print-agent-fields",
        action="store_true",
        default=False,
        help="Print detailed per-field agent comparison results after each test",
    )


def pytest_configure(config):
    """Generate and set a single session ID for the entire test run.

    For pytest-xdist parallel execution, the controller process generates
    the session_id and shares it with workers via environment variable.
    """
    global _PRINT_AGENT_FIELDS

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

            # Get evaluation result if test was run
            eval_result = None
            if hasattr(case, "_eval_result") and case._eval_result is not None:
                eval_result = case._eval_result.model_dump()

            def serialize_for_xdist(obj):
                """Convert enums, sets, and Pydantic models to serializable types for pytest-xdist.

                This recursively processes dictionaries, lists, and other structures
                to convert enums to their string values, sets to lists, and Pydantic
                models to dicts.
                """
                if isinstance(obj, Enum):
                    return obj.value
                elif isinstance(obj, set):
                    return list(obj)
                elif isinstance(obj, BaseModel):
                    # Handle Pydantic models by converting to dict
                    return serialize_for_xdist(obj.model_dump())
                elif isinstance(obj, dict):
                    return {k: serialize_for_xdist(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [serialize_for_xdist(item) for item in obj]
                else:
                    return obj

            session_id = getattr(case, "session_id", None)

            # Build summaries for strict and LLM evaluations if available
            strict_summary = None
            llm_summary = None

            try:
                if getattr(case, "strict_eval_results", None):
                    strict_passed = all(r.passed for r in case.strict_eval_results)
                    strict_rationale = case.strict_eval_results[0].rationale
                    strict_summary = {
                        "passed": strict_passed,
                        "rationale": strict_rationale,
                    }
                if getattr(case, "llm_eval_results", None):
                    llm_passed = all(r.passed for r in case.llm_eval_results)
                    llm_rationale = case.llm_eval_results[0].rationale
                    llm_summary = {"passed": llm_passed, "rationale": llm_rationale}
            except Exception:
                # Best-effort; do not break reporting if structure changes
                pass

            # Serialize all data for xdist compatibility
            report.agent_test_case_data = serialize_for_xdist(
                {
                    "name": case.name,
                    "agent": {
                        "name": case.agent.name,
                    },
                    "prompt_kwargs": {
                        # Truncate large fields for readability
                        k: (
                            v[:5000] + "... [Truncated]"
                            if isinstance(v, str) and len(v) > 5000
                            else v
                        )
                        for k, v in case.prompt_kwargs.items()
                    },
                    "expected_output": case.expected_dict,
                    "actual_outputs": [
                        result.model_dump() for result in (case.results or [])
                    ],
                    "evaluation_config": {
                        "strict_fields": serialize_for_xdist(case.strict_fields),
                        "llm_fields": serialize_for_xdist(case.llm_fields),
                        "evaluator_model": case.evaluator_model,
                        "run_count": case.run_count,
                    },
                    "evaluation_result": eval_result,
                    "strict_summary": strict_summary,
                    "llm_summary": llm_summary,
                    "session_id": session_id,
                }
            )


@pytest.hookimpl()
def pytest_runtest_logreport(report):
    """Collect AgentTestCase data from worker processes into main process dict.

    This hook runs in the main process and receives reports from all workers,
    making it compatible with pytest-xdist parallel execution.
    """
    if hasattr(report, "agent_test_case_data"):
        _agent_test_case_data[report.nodeid] = report.agent_test_case_data

        # Optionally print summaries and per-field comparison details after the test
        if _PRINT_AGENT_FIELDS:
            data = report.agent_test_case_data
            eval_result = (data or {}).get("evaluation_result") or {}
            strict_summary = (data or {}).get("strict_summary") or {}
            llm_summary = (data or {}).get("llm_summary") or {}
            field_comparisons = eval_result.get("field_comparisons") or []
            if field_comparisons:
                print(f"\n=== Agent Field Comparisons: {data.get('name')} ===")
                # Print high-level summaries first
                if strict_summary:
                    status = "PASS" if strict_summary.get("passed") else "FAIL"
                    print(
                        f"Strict Summary: {status} \n  -> Rationale: {strict_summary.get('rationale')}"
                    )
                if llm_summary:
                    status = "PASS" if llm_summary.get("passed") else "FAIL"
                    print(
                        f"LLM Summary: {status} \n  -> Rationale: {llm_summary.get('rationale')}"
                    )

                for fc in field_comparisons:
                    status = "PASS" if fc.get("passed") else "FAIL"
                    field_path = fc.get("field_path")
                    comp_type = fc.get("comparison_type")
                    strategy = fc.get("matching_strategy")
                    total = fc.get("total_instances")
                    passed = fc.get("passed_instances")
                    failed = fc.get("failed_instances")
                    rationale = fc.get("rationale")
                    print(
                        f"[{status}] {field_path}  type={comp_type}  matched={passed}/{total}  strategy={strategy or '-'}"
                    )
                    print(f"  -> Passed: {passed}, Failed: {failed}")
                    print(f"  -> Rationale: {rationale}")

                    # Print expected/actual values for both passing and failing fields
                    expected_output = data.get("expected_output")
                    actual_outputs = data.get("actual_outputs") or []
                    actual_output = actual_outputs[0] if actual_outputs else None

                    # Extract just the field value using the field path
                    parts = (field_path or "").split(".")
                    expected_field_value = _extract_by_path(expected_output, parts)
                    actual_field_value = _extract_by_path(actual_output, parts)

                    status_label = "PASSED" if fc.get("passed") else "FAILED"
                    print(f"\n {field_path} {status_label}")
                    print("  Expected Result:")
                    try:
                        print(
                            json.dumps(
                                expected_field_value, indent=2, ensure_ascii=False
                            )
                        )
                    except Exception:
                        print(expected_field_value)

                    print("  Actual Result (first run):")
                    try:
                        print(
                            json.dumps(actual_field_value, indent=2, ensure_ascii=False)
                        )
                    except Exception:
                        print(actual_field_value)
                    print("\n")

                print("=== End Agent Field Comparisons ===\n")


@pytest.hookimpl()
def pytest_json_modifyreport(json_report):
    """Modify the JSON report to include AgentTestCase metadata."""
    # Add agent_test_case data to each test
    for test in json_report.get("tests", []):
        nodeid = test.get("nodeid")
        if nodeid in _agent_test_case_data:
            test["agent_test_case"] = _agent_test_case_data[nodeid]


def data_path(path: str) -> str:
    """
    Convert relative test data path to absolute path.

    Args:
        path: Relative path from tests/ directory (e.g., "data/common_knowledge/main.md")

    Returns:
        Absolute path to the file
    """
    return str(TESTS_DIR / path)


async def load_document(path: str):
    """
    Load a single document from test data.

    Args:
        path: Relative path from tests/ directory

    Returns:
        FileDocument object with markdown content
    """
    return await create_file_document_from_path(data_path(path))


async def load_document_markdown(path: str) -> str:
    """
    Load document and return only the markdown content.

    Args:
        path: Relative path from tests/ directory

    Returns:
        Markdown string content
    """
    doc = await load_document(path)
    return doc.markdown


async def build_supporting_documents_block(paths: list[str]) -> str:
    """
    Build supporting documents block from file paths.

    Loads multiple documents and concatenates them with separators,
    suitable for passing to agent prompts.

    Args:
        paths: List of relative paths from tests/ directory

    Returns:
        Concatenated markdown with "---" separators, or empty string if no paths
    """
    if not paths:
        return ""

    docs = []
    for path in paths:
        doc = await load_document(path)
        docs.append(doc.markdown)

    return "\n\n---\n\n".join(docs)


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
