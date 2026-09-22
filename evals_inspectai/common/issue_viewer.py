"""Log-viewer defaults shared by the issue-inventory evals.

One narrow, colour-graded column per check, grouped by sample so the epochs
of a document sit side by side; target and answer hidden, since an inventory
eval has no target or answer text. Each eval passes the (scorer, key) columns
it scores and any labels of its own.
"""

from typing import Mapping, Sequence

from inspect_ai.viewer import (
    SampleScoreView,
    SampleScoreViewSort,
    ScoreColorScale,
    TaskSamplesColumn,
    TaskSamplesSort,
    TaskSamplesView,
    ViewerConfig,
)

from evals_inspectai.common.issue_checks import issue_check_keys

# Short column labels for the generic checks; compact score columns show these
# with rotated headers.
SCORE_LABELS: dict[str, str] = {
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
}


def decoy_labels(reasons: Sequence[str]) -> dict[str, str]:
    return {f"no_fp_{r}": f"No FP {r}" for r in reasons}


def issue_viewer_config(
    decoy_reasons: Sequence[str],
    edits: bool = True,
    extra: Sequence[tuple[str, str]] = (),
    labels: Mapping[str, str] | None = None,
    titles: bool = True,
) -> ViewerConfig:
    """Columns for the generic scorers, derived from what they emit given the
    dataset (``issue_checks(edits=..., titles=...)`` and ``decoy_checks(decoy_reasons)``),
    followed by ``extra`` (scorer name, score key) pairs for the eval's own
    scorers; ``labels`` adds headers for those.

    Every emitted key must be listed: the viewer appends any score column the
    config does not mention after its built-in columns, and it decides a score
    column's visibility from the score picker, not from ``visible``. A key an
    eval cannot score should not be emitted at all rather than listed and hidden.
    """
    scored = [
        *(("issue_checks", key) for key in issue_check_keys(edits, titles)),
        *(("decoy_checks", f"no_fp_{reason}") for reason in decoy_reasons),
        *extra,
    ]
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
            score_labels={**SCORE_LABELS, **decoy_labels(decoy_reasons), **(labels or {})},
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
