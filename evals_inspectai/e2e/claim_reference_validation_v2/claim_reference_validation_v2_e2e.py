"""End-to-end eval for the claim_reference_validation_v2 workflow.

Drives the full API path: upload main + supporting files, wait for the
human-approval gate to become PENDING, approve it, then poll for the v2
workflow to complete and score against the same dataset used by the
internal eval.

Backend must be running (`uv run dev.py`).
"""

import json
import logging
from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    mean,
    scorer,
    stderr,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver

from evals_inspectai.common.api_client import (
    approve_workflow_run,
    poll_until_complete,
    poll_until_status,
    upload_and_start_analysis,
)
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.scorers import model_graded_check

logger = logging.getLogger(__name__)

# Shared dataset — single source of truth used by both the e2e and internal evals.
_DATASET_PATH = Path(__file__).parent / "dataset.json"

_TARGET_WORKFLOW = "claim_reference_validation_v2"
_HUMAN_APPROVAL_WORKFLOW = "human_approval"


@task
def claim_reference_validation_v2_e2e():
    dataset = json_dataset(str(_DATASET_PATH), _record_to_sample)
    # Filter out samples that don't make sense for full-document analysis
    # (e.g. section-bound tests that rely on a manual section range).
    dataset = dataset.filter(lambda s: not s.metadata.get("skip_e2e"))

    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=claim_reference_validation_v2_e2e_solver(),
        scorer=[
            citation_alignment_match(),
            citation_count_match(),
            model_graded_check(
                target_from_metadata="target_answer", partial_credit=True
            ),
        ],
    )


def _record_to_sample(record: dict[str, Any]) -> Sample:
    metadata = {
        "main_doc": record["main_doc"],
        "supporting_files": record.get("supporting_files", []),
        "references": record.get("references", []),
        "expected_issues": record.get("expected_issues", []),
        "target_answer": record.get("target_answer", ""),
        "skip_e2e": record.get("skip_e2e", False),
    }

    return Sample(
        id=record.get("id"),
        input=f"{len(record.get('references', []))} references, "
        f"{len(record.get('expected_issues', []))} expected issues",
        target="",
        metadata=metadata,
    )


@solver
def claim_reference_validation_v2_e2e_solver(
    timeout_s: float = 600,
    poll_interval_s: float = 5,
) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        meta = state.metadata or {}

        supporting = [
            (sf.get("file_name", f"{sf['file_id']}.md"), sf["markdown"])
            for sf in meta.get("supporting_files", [])
        ]

        project_id = await upload_and_start_analysis(
            file_content=meta["main_doc"],
            file_name="main.md",
            workflow_types=[_TARGET_WORKFLOW],
            supporting_files=supporting,
        )

        # Wait for the human-approval gate to be ready (PENDING means upstream
        # deps have completed and the gate is awaiting trigger).
        approval_detail = await poll_until_status(
            project_id=project_id,
            workflow_type=_HUMAN_APPROVAL_WORKFLOW,
            target_statuses={"pending", "running", "completed"},
            timeout_s=timeout_s,
            interval_s=poll_interval_s,
        )
        approval_run_id = approval_detail["run"]["id"]
        if approval_detail["run"]["status"] != "completed":
            await approve_workflow_run(approval_run_id)

        try:
            run_detail = await poll_until_complete(
                project_id=project_id,
                workflow_type=_TARGET_WORKFLOW,
                timeout_s=timeout_s,
                interval_s=poll_interval_s,
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}
        state.output = ModelOutput(
            completion=json.dumps(workflow_state),
            model="api",
        )
        return state

    return solve


def _parse_citation_issues(completion: str) -> list[dict[str, Any]]:
    """Extract the citation_issues list from the v2 workflow state."""
    workflow_state = json.loads(completion)
    return workflow_state.get("citation_issues", []) or []


def _evidence_alignment(issue: dict[str, Any]) -> str:
    val = issue.get("evidence_alignment")
    if isinstance(val, dict):
        return val.get("value", "")
    return val or ""


@scorer(metrics=[mean(), stderr()])
def citation_alignment_match():
    """Fraction of expected_issues that match a produced issue by quoted-text
    substring AND have the expected evidence_alignment value."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            issues = _parse_citation_issues(state.output.completion)
        except Exception as e:  # noqa: BLE001
            return Score(value=INCORRECT, explanation=f"Parse error: {e}")

        expected: list[dict[str, Any]] = state.metadata.get("expected_issues", []) or []
        if not expected:
            return Score(value=CORRECT, explanation="No expected_issues declared")

        matches = 0
        notes: list[str] = []
        for exp in expected:
            needle = exp["quoted_contains"].lower()
            found = next(
                (i for i in issues if needle in (i.get("quoted_text") or "").lower()),
                None,
            )
            if not found:
                notes.append(f"missing citation containing '{exp['quoted_contains']}'")
                continue
            actual = _evidence_alignment(found)
            if actual != exp["alignment"]:
                notes.append(
                    f"'{exp['quoted_contains']}' got {actual}, expected {exp['alignment']}"
                )
                continue
            matches += 1

        score_value = matches / len(expected)
        if score_value == 1.0:
            return Score(
                value=CORRECT, explanation=f"All {matches} expected issues matched"
            )
        return Score(
            value=score_value if score_value > 0 else INCORRECT,
            explanation="; ".join(notes) or "no expected issues matched",
        )

    return score


@scorer(metrics=[mean(), stderr()])
def citation_count_match():
    """1.0 if the workflow produced exactly the expected number of issues."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            issues = _parse_citation_issues(state.output.completion)
        except Exception as e:  # noqa: BLE001
            return Score(value=INCORRECT, explanation=f"Parse error: {e}")

        expected = state.metadata.get("expected_issues", []) or []
        if len(issues) == len(expected):
            return Score(value=CORRECT, explanation=f"Issue count matches: {len(issues)}")
        return Score(
            value=INCORRECT,
            explanation=f"Got {len(issues)} issues, expected {len(expected)}",
        )

    return score
