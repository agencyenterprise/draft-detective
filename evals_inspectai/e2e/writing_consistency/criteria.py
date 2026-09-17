"""What Writing Consistency is judged on, beyond the generic layers.

A consistency edit changes one variant to the consistent form and nothing
else. ``minimal_change`` checks that deterministically; the graded criterion
checks the sentence still says what it said.
"""

from typing import Optional

from evals_inspectai.common.issue_inventory import normalize
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import ProposedEdit

MAX_CHANGED_WORDS = 3


def _changed_words(a: str, b: str) -> int:
    """Words that differ between two texts, ignoring the shared prefix and suffix."""
    x, y = normalize(a).split(), normalize(b).split()
    i = 0
    while i < min(len(x), len(y)) and x[i] == y[i]:
        i += 1
    j = 0
    while j < min(len(x), len(y)) - i and x[-1 - j] == y[-1 - j]:
        j += 1
    return max(len(x) - i - j, len(y) - i - j)


def minimal_change(edit: ProposedEdit) -> Optional[bool]:
    """The replacement differs from the original by at most a few words: the
    variant and its immediate neighbours, nothing else. None for a deletion."""
    if not edit.replacement_text.strip():
        return None
    return _changed_words(edit.original_text, edit.replacement_text) <= MAX_CHANGED_WORDS


EXTRA_EDIT_CHECKS = {"minimal_change": minimal_change}
EXTRA_EDIT_DESCRIPTIONS = {
    "edit_minimal_change": (
        f"Share of edits that change at most {MAX_CHANGED_WORDS} words of the original: the variant and nothing else."
    ),
}

MEANING_CRITERION = (
    "The replacement changes one variant in the original sentence to the document's consistent form and "
    "changes nothing else. The consistent form was chosen from the whole document, which you do not see, so "
    "treat whatever the replacement uses as the chosen form and do not judge the choice: swapping one name for "
    "another the document uses for the same thing (participants for respondents), one spelling or hyphenation "
    "for another (healthcare for health care, next-generation for next generation), a number style (7 percent "
    "for 7%), a finding's verb tense, or the house-style compound \"decisionmaking\" (one word, no hyphen, a "
    "deliberate style rather than a misspelling) are all the intended change. Judge only that nothing beyond "
    "the variant moved: every claim, qualifier, number, date, citation and footnote marker survives, no other "
    "wording is altered, and the sentence still refers to the same thing. It is incorrect if the edit rewrites "
    "more than the variant, changes what the sentence asserts, or alters text inside a quotation, a title or a "
    "citation."
)

JUDGE_DESCRIPTIONS = {
    "edit_meaning_preserved": "Graded per edit: only the inconsistent variant changed, to the consistent form, with the sentence's meaning intact (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [JudgeCriterion(key="edit_meaning_preserved", criterion=MEANING_CRITERION, scope="edit")]

SCORE_LABELS = {"edit_minimal_change": "Minimal change", "edit_meaning_preserved": "Meaning"}
