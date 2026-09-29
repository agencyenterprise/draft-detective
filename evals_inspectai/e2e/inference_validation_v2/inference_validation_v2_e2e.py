"""E2E eval for the Inference Validation workflow, on the issue-inventory structure.

Declared by ``skills/inference-validation/SKILL.md``; runs through the API like
every other e2e eval. The workflow runs three detection passes and a separate
adjudicator, and reports one "Invalid Inference: <flaw>" issue per surviving
finding, anchored on the sentence that draws the conclusion.

Ground truth is ``dataset.yaml``: sound reasoning the adjudicator must keep
(a bounded conclusion, a randomized trial with a confidence interval, modus
ponens and modus tollens, a probability sample with its margin of error, a
hedged claim, a claim proportionate to a cited meta-analysis, a document with
no argument at all); one document per recognised fallacy (hasty and
self-selected generalization, post hoc, affirming the consequent, denying the
antecedent, false dichotomy, slippery slope, irrelevant authority, circular
reasoning, the ecological fallacy, composition, survivorship bias, base-rate
neglect, argument from ignorance, correlation read as causation, multiple
comparisons, equivocation on "significant"); a sentence with two flaws, which
the skill reports as one issue; section-length reports mixing flawed and
sound inferences; and a pair of documents with identical text whose chart
either contradicts or supports the premise. Decoys mark the sound inferences,
by the adjudicator's reason for rejecting them.

Scorers: the reusable ``issue_checks`` and ``decoy_checks`` (one issue per
sentence, so matching is ``one_to_one``; severity is the adjudicator's call and
is not checked), this workflow's own deterministic checks of the reporting
contract, and two judged criteria (the analysis names the labelled flaw; the
action repairs it). No ``tool_called("view_image")``: the workflow delegates
the reading to sub-agents whose transcripts are not persisted, so the
orchestrator's messages cannot show the call. The figure pair is built so
detection only passes if a chart was read.

Run (backend must be running)::

    uv run inspect eval evals_inspectai/e2e/inference_validation_v2/inference_validation_v2_e2e.py --epochs 3
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.scorer import Scorer, scorer

from evals_inspectai.common.api_solver import api_workflow_agent
from evals_inspectai.common.issue_checks import (
    DETECTION_DESCRIPTIONS,
    PER_KEY_METRICS,
    decoy_checks,
    decoy_descriptions,
    deterministic_scorer,
    issue_check_keys,
    issue_checks,
)
from evals_inspectai.common.issue_inventory import (
    decoy_reasons,
    expects_severities,
    inventory_dataset,
    load_inventory_records,
)
from evals_inspectai.common.issue_judge import judged_criteria
from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.inference_validation_v2.criteria import (
    JUDGE_CRITERIA,
    JUDGE_DESCRIPTIONS,
    OWN_DESCRIPTIONS,
    SCORE_LABELS,
    inference_scores,
)

WORKFLOW_TYPE = "inference_validation_v2"
DATASET = Path(__file__).parent / "dataset.yaml"


@scorer(metrics=PER_KEY_METRICS)
def inference_checks() -> Scorer:
    """This workflow's own deterministic checks: no informational issue, the flaw named
    in the title, the key sentence quoted verbatim."""
    return deterministic_scorer(inference_scores)


@task
def inference_validation_v2_e2e(timeout_s: float = 600, judge_calls: int = 1) -> Task:
    """Run Inference Validation on every sample and score it against the inventory.

    Args:
        timeout_s: How long to wait for one workflow run through the API.
        judge_calls: Grader calls per graded issue; the median grade is kept.
    """
    records = load_inventory_records(DATASET)
    reasons = list(decoy_reasons(records))
    severities = expects_severities(records)
    keys = issue_check_keys(edits=False, severities=severities)
    own = [
        *(("inference_checks", key) for key in OWN_DESCRIPTIONS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return Task(
        dataset=inventory_dataset(records, DATASET),
        metadata={
            "ground_truth": (
                "Inventory: one expected issue per invalid inference, anchored on the sentence that draws it and "
                "carrying the labeller's account of the flaw; sound documents expect none. Decoys are sound "
                "inferences a correct run leaves alone. Severity is not checked and no edits are expected. A NaN "
                "metric value means the sample gave that check nothing to judge."
            ),
            "metrics": {
                "issue_checks": {k: v for k, v in DETECTION_DESCRIPTIONS.items() if k in keys},
                "decoy_checks": decoy_descriptions(reasons),
                "inference_checks": OWN_DESCRIPTIONS,
                "judged_criteria": JUDGE_DESCRIPTIONS,
            },
        },
        solver=api_workflow_agent(WORKFLOW_TYPE, timeout_s=timeout_s),
        scorer=[
            issue_checks(edits=False, one_to_one=True, severities=severities),
            decoy_checks(reasons),
            inference_checks(),
            judged_criteria(JUDGE_CRITERIA, calls=judge_calls, one_to_one=True),
        ],
        fail_on_error=0.2,
        viewer=issue_viewer_config(reasons, edits=False, extra=own, labels=SCORE_LABELS, severities=severities),
    )
