"""What Active Voice & Clear Actors is judged on, beyond the generic layers.

The generic inventory scorer checks that expected issues were detected and that
edits keep the text intact. This module says what an Active Voice edit must
do on top: remove the passive (deterministic), preserve meaning while naming
the actor the text supports, read well in place, and, where the actor is
unknown, ask the author rather than guess (graded). The two edit criteria are
calibrated against human-labelled edit pairs by
``active_voice_judge_calibration.py``.
"""

import re
from typing import Optional

from evals_inspectai.common.simple_deep_agent_types import ProposedEdit
from evals_inspectai.common.issue_inventory import ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion

PASSIVE_TITLE = "Passive Voice"
AMBIGUOUS_TITLE = "Ambiguous Actor"

# A form of be or get, optionally chained ("are being made", "has been sent"),
# any run of adverbs or negation ("were not considered", "was first proposed",
# "is widely regarded"), then the candidate participle.
_BE_PLUS_WORD_RE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|get|gets|got|gotten|getting)(?:\s+(?:being|been))?"
    r"(?:\s+(?:not|never|also|then|first|later|already|still|often|once|now|thus|\w+ly))*"
    r"\s+(\w+)\b",
    re.I,
)
# Past participles the suffix test below cannot see.
_IRREGULAR_PARTICIPLES = frozenset(
    "sent built made held done paid laid said kept left lost put set shown known seen drawn withdrawn found met "
    "read spent cut led fed meant felt dealt sold told understood brought thought bought caught taught sought fought "
    "begun run won sung hung struck stuck lent bent split shut hit spread born borne worn torn sworn undertaken "
    "overseen cast forecast broadcast let shed upset hurt quit bound wound ground spun dug slid lit shot fit thrust "
    "burnt learnt spelt dreamt knit".split()
)
# Words a suffix test would take for participles.
_NOT_PARTICIPLES = frozenset("even seven then when open often none need indeed".split())
_PARTICIPLE_SUFFIXES = ("ed", "en", "own", "ought", "aught", "uilt", "ade", "eld", "one", "aid")


def _is_participle(word: str) -> bool:
    w = word.lower()
    if w in _IRREGULAR_PARTICIPLES:
        return True
    if w in _NOT_PARTICIPLES or len(w) < 4:
        return False
    return w.endswith(_PARTICIPLE_SUFFIXES)


def passive_count(text: str) -> int:
    """How many be-plus-participle constructions the heuristic sees in ``text``."""
    return sum(1 for word in _BE_PLUS_WORD_RE.findall(text) if _is_participle(word))


def removes_passive(edit: ProposedEdit) -> Optional[bool]:
    """The replacement has fewer be-plus-participle constructions than the original.

    None when the heuristic sees no passive in the original: there is nothing
    to credit or blame, so the edit is left out of the fraction rather than
    passed by default.
    """
    before = passive_count(edit.original_text)
    if before == 0:
        return None
    return passive_count(edit.replacement_text) < before


EXTRA_EDIT_CHECKS = {"removes_passive": removes_passive}
EXTRA_EDIT_DESCRIPTIONS = {
    "edit_removes_passive": (
        "Share of edits whose replacement has fewer be-plus-participle constructions than the original "
        "(regex heuristic). Edits whose original shows the heuristic no passive are not scored."
    ),
}


MEANING_CRITERION = (
    "The replacement rewrites the original from passive into active voice and preserves its meaning. "
    "Naming the actor the passive left implicit is the purpose of the edit and does not count as adding "
    "information, as long as the actor named is the one the sentence or its paragraph supports (for a report "
    "written in the first person, the authors as \"we\"). Everything else is strict: every claim, qualifier, "
    "number, date, citation and footnote marker in the original survives with the same meaning, no other "
    "information is added, and the actor is not a guess the text does not support."
)

READS_CRITERION = (
    "Substituted into its paragraph, the replacement reads at least as clearly and naturally as the original. "
    "The change from passive to active (often by naming the actor or using \"we\") is intended and is not a "
    "defect; whether the content is preserved is graded separately and must be ignored here. Mark it incorrect "
    "only for a clear defect a careful editor would fix: ungrammatical or hard-to-parse word order; a subject "
    "longer than about twelve words before the verb; the paragraph's topic pushed out of subject position; a "
    "needless repetition, including of a phrase the previous sentence just used; or doubled, stranded or "
    "missing punctuation. Small differences in rhythm or emphasis are correct."
)

ACTOR_CRITERION = (
    "The sentence was flagged because its passive voice hides who performs the action and the document does "
    "not say who. The suggested action asks the author to name who performs the action, without itself "
    "asserting or guessing who that is. It is incorrect if it names or implies an actor, or proposes a rewrite "
    "that supplies one."
)


def _unknown_actor_passive(expected: ResolvedIssue) -> bool:
    return expected.title == PASSIVE_TITLE and expected.edit_expected is False


JUDGE_DESCRIPTIONS = {
    "edit_meaning_preserved": "Graded per edit: the active rewrite keeps every claim, number, citation and qualifier, naming only the actor the text supports (C=1, P=0.5, I=0).",
    "edit_reads_well": "Graded per edit: substituted into its paragraph, the replacement reads at least as well as the original (C=1, P=0.5, I=0).",
    "unknown_actor_asked_not_guessed": "Graded per passive issue with no edit expected: the suggested action asks the author to name the actor rather than supplying one (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(key="edit_meaning_preserved", criterion=MEANING_CRITERION, scope="edit"),
    JudgeCriterion(key="edit_reads_well", criterion=READS_CRITERION, scope="edit"),
    JudgeCriterion(
        key="unknown_actor_asked_not_guessed",
        criterion=ACTOR_CRITERION,
        scope="expected",
        applies_to=_unknown_actor_passive,
    ),
]
