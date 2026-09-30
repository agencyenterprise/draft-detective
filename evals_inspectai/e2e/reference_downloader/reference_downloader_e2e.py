"""E2E eval for the Reference Downloader workflow.

Declared by ``skills/reference-download/SKILL.md``. For each reference the
workflow searches the web for the full original content, downloads a
candidate, verifies it, and concludes found, found but not accessible, or not
found; a found file is kept in the project as a supporting document, and every
other download is cleaned up.

Ground truth is ``dataset.yaml``: references of many kinds (reports,
articles, preprints, testimony, doctrine, a public law, press releases, a
database, a homepage, a social post, a paywalled forecast, fabricated
references), each with the conclusions a correct run may reach and phrases
the downloaded file must contain (see ``records``).

The solver runs the workflow the way the app does (upload the document, run
document processing and reference extraction, start the downloader for the
reference) and then reads the project's files back through the app's file
listing, so ``download_checks`` scores the file the app kept, not the agent's
account of it, and ``download_judged`` grades from the file's opening, end and
length whether it is the complete work rather than a preview or excerpt.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/reference_downloader/reference_downloader_e2e.py --epochs 3
"""

import json
import math
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState

from evals_inspectai.common.api_client import (
    create_project_and_start_workflows,
    get_project_files,
    poll_workflow_run_until_complete,
    start_workflow,
)
from evals_inspectai.common.api_solver import surface_conversations
from evals_inspectai.common.errors import WorkflowCompletionError
from evals_inspectai.common.issue_checks import PER_KEY_METRICS
from evals_inspectai.common.issue_judge import gist, grade
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.common.model_override import output_model_name
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.e2e.reference_downloader.records import (
    DESCRIPTIONS,
    FOUND,
    JUDGE_DESCRIPTIONS,
    KEYS,
    DownloaderOutput,
    DownloadRecord,
    download_dataset,
    completeness_prompt,
    download_scores,
    kept_file,
    load_records,
)

DATASET = Path(__file__).parent / "dataset.yaml"
# A downloaded file's text is kept only this far from each end: its title page and
# opening, and its last pages, where a preview's subscription prompts or a complete
# work's references show; its full length is kept too. Whole reports stay out of the log.
MARKDOWN_KEPT = 40_000
MARKDOWN_TAIL = 8_000

SCORE_LABELS = {
    "conclusion_accepted": "Conclusion",
    "file_kept_when_found": "File kept",
    "file_matches_reference": "File matches",
    "no_file_when_not_found": "No stray file",
    "reason_when_inaccessible": "Reason",
    "url_when_found": "URL",
    "file_is_complete": "Complete",
}


@agent
def _reference_downloader_api_agent(timeout_s: float = 600, poll_interval_s: float = 5) -> Agent:
    """Run the reference_downloader workflow via the API for one reference, then read
    the project's files back through the app's file listing."""

    async def execute(state: AgentState) -> AgentState:
        reference = state.messages[0].text if state.messages else ""
        project_id = await create_project_and_start_workflows(
            file_content=f"## References\n\n{reference}",
            file_name="eval-document.md",
            workflow_types=["document_processing", "reference_extraction"],
        )
        workflow_run_id = await start_workflow(
            {
                "type": "reference_downloader",
                "project_id": project_id,
                "references": [{"reference_id": "ref-1", "text": reference}],
            }
        )
        try:
            run_detail = await poll_workflow_run_until_complete(
                workflow_run_id, timeout_s=timeout_s, interval_s=poll_interval_s
            )
        except TimeoutError as e:
            raise WorkflowCompletionError(str(e)) from e

        workflow_state = run_detail.get("state") or {}
        _check_item_errors(workflow_state)
        workflow_state["project_files"] = [
            {
                "id": str(f.get("id")),
                "role": f.get("role") or "",
                "file_name": f.get("file_name") or "",
                "markdown": (f.get("markdown") or "")[:MARKDOWN_KEPT],
                "markdown_tail": (f.get("markdown") or "")[-MARKDOWN_TAIL:],
                "markdown_chars": len(f.get("markdown") or ""),
            }
            for f in await get_project_files(project_id)
        ]
        await surface_conversations(
            state, workflow_state, "reference_downloader", item_messages_key="fetched_references", item_label="reference"
        )
        state.output = ModelOutput(completion=json.dumps(workflow_state), model=output_model_name(run_detail))
        return state

    return execute


def _check_item_errors(workflow_state: dict) -> None:
    """Raise if any fetched reference has a per-item error."""
    for item in workflow_state.get("fetched_references", []):
        if isinstance(item, dict) and item.get("error"):
            raise WorkflowCompletionError(f"Reference '{item.get('input_reference', '?')}' failed: {item['error']}")


@scorer(metrics=PER_KEY_METRICS)
def download_checks() -> Scorer:
    """The conclusion and the file the app kept, one key per check (see ``records.download_scores``)."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = DownloaderOutput.model_validate_json(state.output.completion)
        except ValueError as e:
            return Score(value={k: 0.0 for k in KEYS}, explanation=f"could not parse the workflow state: {e}")
        item = output.fetched_references[0].result if output.fetched_references else None
        if item is None:
            return Score(value={k: 0.0 for k in KEYS}, explanation="no fetch result")
        record = DownloadRecord.model_validate(state.metadata["record"])
        values, explanation = download_scores(item, output.project_files, record)
        return Score(value=values, explanation=explanation)

    return score


@scorer(metrics=PER_KEY_METRICS)
def download_judged(calls: int = 1) -> Scorer:
    """Whether the kept file is the complete work, on Inspect's ``grader`` role."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = DownloaderOutput.model_validate_json(state.output.completion)
        except ValueError as e:
            return Score(value={"file_is_complete": 0.0}, explanation=f"could not parse the workflow state: {e}")
        item = output.fetched_references[0].result if output.fetched_references else None
        kept = kept_file(item, output.project_files) if item and item.final_conclusion == FOUND else None
        if kept is None:
            return Score(value={"file_is_complete": math.nan}, explanation="no kept file to judge")
        record = DownloadRecord.model_validate(state.metadata["record"])
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        value, reasoning = await grade(grader, completeness_prompt(record, kept), calls)
        return Score(value={"file_is_complete": value}, explanation=gist(reasoning) if value < 1.0 else "complete")

    return score


@task
def reference_downloader_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Reference Downloader on every reference and check the conclusion and the kept file.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per kept file; the median grade is kept.
    """
    records = load_records(DATASET)
    columns = [*(("download_checks", k) for k in KEYS), ("download_judged", "file_is_complete")]
    return Task(
        dataset=download_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "One reference per record, with the conclusions a correct run may reach and phrases the downloaded "
                "file must contain. A NaN metric value means the conclusion made that check moot."
            ),
            "metrics": {"download_checks": DESCRIPTIONS, "download_judged": JUDGE_DESCRIPTIONS},
        },
        solver=_reference_downloader_api_agent(timeout_s=timeout_s),
        scorer=[download_checks(), download_judged(calls=judge_calls)],
        fail_on_error=0.2,
        viewer=issue_viewer_config(columns, SCORE_LABELS),
    )
