"""What Concision & Precision is judged on, beyond the generic layers.

The generic inventory scorer checks that expected issues were detected and that
edits keep the text intact. This module adds what a concision edit must do on
top: not introduce a passive the original lacked (deterministic), preserve
every claim and qualifier while tightening (graded), and read at least as
well in place (graded).
"""

from typing import Optional

from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.e2e.active_voice.criteria import passive_count

CONCISION_TITLES = ("Wordy Construction", "Run-On Sentence", "Throat-Clearing")
PRECISION_TITLES = ("Vague Reference", "Empty Framing", "Obvious Statement")


def no_added_passive(edit: ProposedEdit) -> Optional[bool]:
    """The replacement has no more be-plus-participle constructions than the
    original: tightening must not introduce passive voice as a side effect.
    None for a deletion, which has nothing to assess."""
    if not edit.replacement_text.strip():
        return None
    return passive_count(edit.replacement_text) <= passive_count(edit.original_text)


EXTRA_EDIT_CHECKS = {"no_added_passive": no_added_passive}
EXTRA_EDIT_DESCRIPTIONS = {
    "edit_no_added_passive": (
        "Share of edits whose replacement has no more be-plus-participle constructions than the original "
        "(regex heuristic); deletions are not scored."
    ),
}

MEANING_CRITERION = (
    "The replacement tightens or sharpens the original sentence and preserves its meaning. Removing filler, "
    "a redundant word, or a wordy phrase in favour of its plain equivalent is the purpose of the edit and does "
    "not count as losing content; naming what a vague reference points to, when the paragraph supports it, "
    "does not count as adding content. Everything else is strict: every claim, qualifier (including source "
    "qualifiers such as \"staff reported\"), hedge, number, date, citation and footnote marker in the original "
    "survives with the same meaning, no clause carrying data or a conclusion is dropped, no new information or "
    "jargon is added, and two sentences are not merged with a semicolon. An empty replacement deletes the "
    "sentence. The sentence was flagged as filler, empty framing or a statement of the obvious, so its general "
    "assertion (\"the picture is complex\", \"funding is essential\", \"there are several things to consider\") "
    "does not count as content: a deletion is correct unless the deleted sentence carried a number, a source "
    "qualifier, a hedge on another claim, a citation, or a specific fact that appears nowhere else in the "
    "paragraph."
)

READS_CRITERION = (
    "Substituted into its paragraph, the replacement reads at least as clearly and naturally as the original. "
    "Being shorter or more direct is intended and is not a defect; whether the content is preserved is graded "
    "separately and must be ignored here. Mark it incorrect only for a clear defect a careful editor would fix: "
    "ungrammatical or hard-to-parse word order; a sentence fragment left by a deletion; a split that leaves a "
    "clause dangling; a repetition the previous sentence just used; or doubled, stranded or missing punctuation. "
    "Small differences in rhythm or emphasis are correct. An empty replacement deletes the sentence: grade "
    "whether the paragraph still reads naturally without it (no dangling reference to the removed sentence, "
    "no orphaned transition)."
)

JUDGE_DESCRIPTIONS = {
    "edit_meaning_preserved": "Graded per edit: the tighter rewrite keeps every claim, qualifier, number and citation, adding nothing but a supported referent (C=1, P=0.5, I=0).",
    "edit_reads_well": "Graded per edit: substituted into its paragraph, the replacement reads at least as well as the original (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(key="edit_meaning_preserved", criterion=MEANING_CRITERION, scope="edit"),
    JudgeCriterion(key="edit_reads_well", criterion=READS_CRITERION, scope="edit"),
]

SCORE_LABELS = {
    "edit_no_added_passive": "No new passive",
    "edit_meaning_preserved": "Meaning",
    "edit_reads_well": "Reads well",
}
