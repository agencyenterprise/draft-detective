"""E2E eval for Abbreviation Scan (v2) on a full-length report and its definition-removed variants.

The same workflow, solver and scorers as ``abbreviation_checker_e2e`` (see its
docstring), over ``dataset_report.yaml``: one published RAND report of 817
lines (``files/benchmarks_report.md``) that the workflow catalogues in many
chunks, and nine copies of it with first inline definitions removed, one per
abbreviation (AI, IRT, VCT, 2PL, HPCT, MBCT, LLM, 1PL) plus one with all eight.
Each copy differs from the report only on the edited lines, so the catalogues
share line numbers and each removal shows up as one catalogue field and, where
the first use becomes bare, one "Abbreviation not defined at first use" issue.

It is its own task because each sample is a long document: running it with the
short samples would multiply their cost and run time. The ground truth also
expects one issue the workflow does not raise yet ("Ambiguous abbreviation" on
the report's "Item response time (IRT)", which its fuzzy definition match
accepts as "Item Response Theory"), so issue recall stays below 1 until that
comparison is tightened.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/abbreviation_checker/abbreviation_checker_report_e2e.py --max-samples 10
"""

from pathlib import Path

from inspect_ai import Task, task

from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import build_task, load_suite

DATASET = Path(__file__).parent / "dataset_report.yaml"


@task
def abbreviation_checker_report_e2e(timeout_s: float = 1800) -> Task:
    """Run Abbreviation Scan on the long report and its variants and score catalogues and persisted issues.

    Args:
        timeout_s: How long to wait for one workflow run through the API; a long report runs many chunks.
    """
    return build_task(load_suite(DATASET, name="abbreviation_checker_report"), timeout_s)
