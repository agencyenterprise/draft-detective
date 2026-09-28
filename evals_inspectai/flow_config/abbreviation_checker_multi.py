"""Run the current chunked abbreviation-scan E2E eval.

Usage:
    uv run flow run evals_inspectai/flow_config/abbreviation_checker_multi.py

Use ``--arg backend=local`` to start and test this checkout's backend.
"""

from pathlib import Path

from inspect_flow import FlowSpec, FlowTask, tasks_matrix

_E2E = Path(__file__).resolve().parent.parent / "e2e" / "abbreviation_checker"

TASK = f"{_E2E}/abbreviation_checker_e2e.py@abbreviation_checker_e2e"


def flow(
    backend: str = "remote",
    api_base_url: str | None = None,
    epochs: int = 3,
) -> FlowSpec:
    """Exercise abbreviation_scan_v2, including its chunk extraction and assembly."""
    return FlowSpec(
        log_dir="logs",
        tasks=tasks_matrix(
            task=FlowTask(name=TASK, epochs=epochs),
            args=[
                {
                    "backend": backend,
                    "api_base_url": api_base_url,
                }
            ],
        ),
    )
