"""Log-viewer defaults for the Active Voice eval: the shared inventory layout
plus this workflow's own columns (its edit check and judged criteria)."""

from inspect_ai.viewer import ViewerConfig

from evals_inspectai.common.issue_viewer import issue_viewer_config
from evals_inspectai.e2e.active_voice.criteria import EXTRA_EDIT_CHECKS, JUDGE_CRITERIA

SCORE_LABELS = {
    "edit_removes_passive": "Passive gone",
    "edit_meaning_preserved": "Meaning",
    "edit_reads_well": "Reads well",
    "unknown_actor_asked_not_guessed": "Asks, no guess",
}


def viewer_config(decoy_reasons: list[str]) -> ViewerConfig:
    own: list[tuple[str, str]] = [
        *(("active_voice_edit_checks", f"edit_{name}") for name in EXTRA_EDIT_CHECKS),
        *(("judged_criteria", c.key) for c in JUDGE_CRITERIA),
    ]
    return issue_viewer_config(decoy_reasons, edits=True, extra=own, labels=SCORE_LABELS)
