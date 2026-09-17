"""Log-viewer defaults for the Active Voice eval.

One narrow, colour-graded column per check, grouped by sample so the three
epochs of a document sit side by side; target and answer hidden, since the
inventory eval has no target or answer text.
"""

from inspect_ai.viewer import (
    SampleScoreView,
    SampleScoreViewSort,
    ScoreColorScale,
    TaskSamplesColumn,
    TaskSamplesSort,
    TaskSamplesView,
    ViewerConfig,
)

from evals_inspectai.common.issue_checks import DETECTION_KEYS, EDIT_KEYS
from evals_inspectai.e2e.active_voice.criteria import EXTRA_EDIT_CHECKS, JUDGE_CRITERIA

# Short column labels; compact score columns show these with rotated headers.
SCORE_LABELS = {
    "recall": "Recall",
    "precision": "Precision",
    "f0_5": "F0.5",
    "clean_document_untouched": "Clean",
    "title_correct": "Title",
    "severity_correct": "Severity",
    "anchor_in_range": "Lines",
    "edit_present_when_expected": "Edit present",
    "edit_absent_when_not_expected": "Edit absent",
    "edit_quote_on_line": "Quote on line",
    "edit_expected_phrases": "Phrasing",
    "edit_keeps_numbers_and_markers": "Numbers kept",
    "edit_punctuation": "Punctuation",
    "edit_removes_passive": "Passive gone",
    "edit_meaning_preserved": "Meaning",
    "edit_reads_well": "Reads well",
    "unknown_actor_asked_not_guessed": "Asks, no guess",
}


def viewer_config(decoy_reasons: list[str]) -> ViewerConfig:
    scored: list[tuple[str, str]] = [
        *(("issue_checks", key) for key in (*DETECTION_KEYS, *EDIT_KEYS)),
        *(("decoy_checks", f"no_fp_{reason}") for reason in decoy_reasons),
        *(("active_voice_edit_checks", f"edit_{name}") for name in EXTRA_EDIT_CHECKS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    labels = {**SCORE_LABELS, **{f"no_fp_{r}": f"No FP {r}" for r in decoy_reasons}}
    return ViewerConfig(
        task_samples_view=TaskSamplesView(
            name="Checks by sample and epoch",
            columns=[
                TaskSamplesColumn(id="sampleStatus"),
                TaskSamplesColumn(id="sampleId"),
                TaskSamplesColumn(id="epoch"),
                TaskSamplesColumn(id="input"),
                *(TaskSamplesColumn.score(scorer, key) for scorer, key in scored),
                TaskSamplesColumn(id="error"),
                TaskSamplesColumn(id="duration"),
                TaskSamplesColumn(id="target", visible=False),
                TaskSamplesColumn(id="answer", visible=False),
                TaskSamplesColumn(id="tokens", visible=False),
            ],
            sort=[
                TaskSamplesSort(column="sampleId", dir="asc"),
                TaskSamplesSort(column="epoch", dir="asc"),
            ],
            compact_scores=True,
            multiline=False,
            score_labels=labels,
            # Pinned to 0..1 so a check that passes everywhere still paints green,
            # rather than the viewer anchoring each palette to the observed range.
            score_color_scales={key: ScoreColorScale(palette="good-high", min=0.0, max=1.0) for _, key in scored},
            color_scales_enabled=True,
        ),
        sample_score_view=SampleScoreView(
            default="grid",
            sort=SampleScoreViewSort(column="value", dir="asc"),
        ),
    )
