"""Smoke-test the end-to-end workflows through Inspect Flow.

Backend models remain deployment-controlled (except the local abbreviation
override). This is not a backend model-comparison matrix; Inspect's model is
used by model-graded scorers. Only one dataset sample per task is selected.

Requires: the project's Inspect Flow dependency
Usage:    uv run flow run evals_inspectai/flow_config/run_all_evals.py
"""

from pathlib import Path

from inspect_flow import (
    FlowOptions,
    FlowSpec,
    FlowTask,
    models_matrix,
    tasks_matrix,
)

_ROOT = Path(__file__).resolve().parents[2]

TASKS = [
    "evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_e2e.py@abbreviation_checker_e2e",
    "evals_inspectai/e2e/about_this_ger/about_this_ger_e2e.py@about_this_ger_e2e",
    "evals_inspectai/e2e/active_voice/active_voice_e2e.py@active_voice_e2e",
    "evals_inspectai/e2e/advocacy_tone_v2/advocacy_tone_v2_e2e.py@advocacy_tone_v2_e2e",
    "evals_inspectai/e2e/claim_reference_validation_v2/claim_reference_validation_v2_e2e.py@claim_reference_validation_v2_e2e",
    "evals_inspectai/e2e/document_structure/document_structure_e2e.py@document_structure_e2e",
    "evals_inspectai/e2e/figures_tables_check/figures_tables_check_e2e.py@figures_tables_check_e2e",
    "evals_inspectai/e2e/inference_validation_v2/inference_validation_v2_e2e.py@inference_validation_v2_e2e",
    "evals_inspectai/e2e/literature_review_v2/literature_review_v2_e2e.py@literature_review_v2_e2e",
    "evals_inspectai/e2e/live_reports_v2/live_reports_v2_e2e.py@live_reports_v2_e2e",
    "evals_inspectai/e2e/methodological_alignment/methodological_alignment_e2e.py@methodological_alignment_e2e",
    "evals_inspectai/e2e/recommendation_check/recommendation_check_e2e.py@recommendation_check_e2e",
    "evals_inspectai/e2e/reference_downloader/reference_downloader_e2e.py@reference_downloader_e2e",
    "evals_inspectai/e2e/reference_text_extractor/reference_text_extractor_e2e.py@reference_text_extractor_e2e",
    "evals_inspectai/e2e/reference_validation_v2/reference_validation_v2_e2e.py@reference_validation_v2_e2e",
    "evals_inspectai/e2e/results_extraction/results_extraction_e2e.py@results_extraction_e2e",
    "evals_inspectai/e2e/reviewer_2/reviewer_2_e2e.py@reviewer_2_e2e",
    "evals_inspectai/e2e/reviewer_coverage_report/reviewer_coverage_report_e2e.py@reviewer_coverage_report_e2e",
    "evals_inspectai/e2e/revision_planning_summary/revision_planning_summary_e2e.py@revision_planning_summary_e2e",
]


def flow(backend: str = "remote", api_base_url: str | None = None) -> FlowSpec:
    """Use --arg backend=local to start repository code, or pass api_base_url."""
    return FlowSpec(
        log_dir="logs",
        options=FlowOptions(limit=1),
        tasks=tasks_matrix(
            task=[FlowTask(name=f"{_ROOT}/{task}", epochs=3) for task in TASKS],
            args=[{"backend": backend, "api_base_url": api_base_url}],
            model=models_matrix(model="openai/gpt-5.6-terra"),
        ),
    )
