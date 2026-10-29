"""What Sentence Structure is judged on, beyond the generic layers.

The generic inventory scorer checks that expected issues were detected and that
edits keep the text intact. This module adds what a restructuring edit must do
on top: cover a single sentence and not introduce a passive the original lacked
(deterministic; the passive check is shared with Concision & Precision), preserve every claim and qualifier while fixing the
structure (graded), and leave a sentence that parses and reads well in place
(graded).
"""

import re

from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.e2e.concision_precision.criteria import no_added_passive

# A sentence end inside the quoted text: terminal punctuation, any closing quotes,
# brackets or Markdown emphasis, whitespace, then the start of the next sentence:
# opening markup (emphasis, a link, code, a quote) before a capital or digit, or an
# opening parenthesis before a capital. A parenthesis before a digit is a citation
# year ("et al. (2024)"), not a new sentence.
_SENTENCE_BREAK_RE = re.compile(
    r"[.!?][\"”’)\]*_`]*\s+(?:[*_\[`“\"]*[A-Z0-9]|\(+[*_`“\"]*[A-Z])"
)


def one_sentence(edit: ProposedEdit) -> bool:
    """The edit stays within one sentence: one that spans two can merge them,
    which the skill forbids. A phrase inside a sentence passes; the check is
    about crossing a sentence break, not about quoting the whole sentence.
    Abbreviations followed by a capital ("U.S. Army") read as a break, so a
    dataset avoids them in sentences it expects edits on."""
    return _SENTENCE_BREAK_RE.search(edit.original_text.strip()) is None


EXTRA_EDIT_CHECKS = {
    "one_sentence": one_sentence,
    "no_added_passive": no_added_passive,
}
EXTRA_EDIT_DESCRIPTIONS = {
    "edit_one_sentence": "Share of edits whose quoted text stays within one sentence (no sentence break inside it; a phrase passes).",
    "edit_no_added_passive": (
        "Share of edits whose replacement has no more be-plus-participle constructions than the original "
        "(regex heuristic); deletions are not scored."
    ),
}

MEANING_CRITERION = (
    "The replacement fixes the structure of the original sentence and preserves its meaning. Supplying a word "
    "the sentence was missing (a verb, a preposition, an object), giving each of two verbs its own object, "
    "moving or completing a correlative (both/and, either/or, not only/but also), putting the items of a "
    "series into one form, or leading a summary sentence with the table, figure or content it introduces "
    '("Table 2 summarizes...", "The following recommendations draw on...", or the authors as "we") is the '
    "purpose of the edit and does not count as changing content. Everything else is strict: every claim, "
    "qualifier, hedge, number, date, citation and footnote marker in the original survives with the same "
    "meaning; neither half of a shared construction loses its meaning; no new information is added; and a "
    "summary sentence still names every source the original listed."
)

READS_CRITERION = (
    "Substituted into its paragraph, the replacement is a grammatical sentence that reads at least as clearly "
    "and naturally as the original. Restructuring is intended and is not a defect; whether the content is "
    "preserved is graded separately and must be ignored here. Mark it incorrect only for a clear defect a "
    "careful editor would fix: a sentence that still does not parse; a pair or series still not parallel; "
    "a pronoun whose referent is unclear; a needless repetition, including of a phrase the previous sentence "
    "just used; or doubled, stranded or missing punctuation. Small differences in rhythm or emphasis are correct."
)

JUDGE_DESCRIPTIONS = {
    "edit_meaning_preserved": "Graded per edit: the restructured sentence keeps every claim, qualifier, number and source, adding only the missing word or the structure the fix needs (C=1, P=0.5, I=0).",
    "edit_reads_well": "Graded per edit: substituted into its paragraph, the replacement parses and reads at least as well as the original (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(
        key="edit_meaning_preserved", criterion=MEANING_CRITERION, scope="edit"
    ),
    JudgeCriterion(key="edit_reads_well", criterion=READS_CRITERION, scope="edit"),
]

SCORE_LABELS = {
    "edit_one_sentence": "One sentence",
    "edit_no_added_passive": "No new passive",
    "edit_meaning_preserved": "Meaning",
    "edit_reads_well": "Reads well",
}
