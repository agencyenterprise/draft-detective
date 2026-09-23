"""Run abbreviation_checker_from_files against the multi-variant dataset.

Usage:
    uv run flow run evals_inspectai/flow_config/abbreviation_checker_multi.py
"""

from pathlib import Path

from inspect_flow import FlowSpec, FlowTask, tasks_matrix

_E2E = Path(__file__).resolve().parent.parent / "e2e" / "abbreviation_checker"

TASK = f"{_E2E}/abbreviation_checker_e2e.py@abbreviation_checker_from_files"


def flow(backend: str = "remote", api_base_url: str | None = None) -> FlowSpec:
    """Use --arg backend=local to start repository code, or pass api_base_url."""
    return FlowSpec(
        log_dir="logs",
        tasks=tasks_matrix(
            task=FlowTask(name=TASK, epochs=10),
            args=[
                {
                    "data_dir": str(_E2E / "data" / "variants" / "multi"),
                    "backend": backend,
                    "api_base_url": api_base_url,
                }
            ],
        ),
    )
