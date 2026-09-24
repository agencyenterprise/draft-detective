"""What Headers & Skimmability is judged on, beyond the generic layers.

The workflow proposes no edits: a new header or lead sentence is wording the
author chooses, so the skill puts it in the suggested action, in a fixed form
(``Suggested header: "..."``, ``Suggested lead: "..."``). The deterministic
checks read that wording back: it is there, a header stays 2 to 8 words, and a
numbered header keeps its number. The judge grades the same wording against the
section it heads, which it sees in full (``passage="section"``).
"""

import math
import re
from typing import Optional, Sequence

from evals_inspectai.common.issue_checks import hit_pairs
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

HEADER_TITLES = ("Vague Header", "Header Lacks Takeaway", "Header Does Not Match Content")
LEAD_TITLE = "Lead Sentence Lacks Takeaway"
MIN_HEADER_WORDS, MAX_HEADER_WORDS = 2, 8

_SUGGESTION_RE = re.compile(r"Suggested (header|lead):\s*[\"“](.+?)[\"”]", re.I)
# "Chapter 3:", "Appendix B:", "3.", "2.1", "2.1.4" at the start of a header.
_NUMBER_RE = re.compile(r"^\s*((?:chapter|appendix|part)\s+[\dA-Z]+[:.]?|\d+(?:\.\d+)*\.?)\s+", re.I)


def is_header_issue(expected: ResolvedIssue) -> bool:
    return expected.title in HEADER_TITLES


def takes_suggestion(expected: ResolvedIssue) -> bool:
    """Header and lead-sentence issues carry suggested wording; the others do not."""
    return is_header_issue(expected) or expected.title == LEAD_TITLE


def suggestion(action: Optional[str], kind: str) -> Optional[str]:
    """The wording after ``Suggested <kind>:`` in a suggested action, or None."""
    for match in _SUGGESTION_RE.finditer(action or ""):
        if match.group(1).lower() == kind:
            return header_text(match.group(2))
    return None


def header_text(line: str) -> str:
    """A markdown header line without its hashes or emphasis."""
    return line.lstrip("#").strip().strip("*").strip()


def section_number(header: str) -> Optional[str]:
    match = _NUMBER_RE.match(header)
    return match.group(1).rstrip(":.").lower() if match else None


def header_words(header: str) -> int:
    """Words in a header, not counting its section number."""
    return len(_NUMBER_RE.sub("", header, count=1).split())


def _fraction(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else math.nan


SUGGESTION_KEYS = ("suggestion_in_form", "suggestion_header_length", "suggestion_keeps_number")


def suggestion_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """Over detected header and lead-sentence issues: the suggested wording is given in
    the skill's form, a suggested header is header-length, and a numbered header keeps
    its number. NaN where a sample has nothing of the kind."""
    lines = inventory.document.split("\n")
    in_form: list[float] = []
    length: list[float] = []
    number: list[float] = []
    notes: list[str] = []
    for expected, issue in hit_pairs(issues, inventory, one_to_one=True)[1]:
        if not takes_suggestion(expected):
            continue
        kind = "header" if is_header_issue(expected) else "lead"
        wording = suggestion(issue.suggested_action, kind)
        in_form.append(float(wording is not None))
        if wording is None:
            notes.append(f"{expected.id}: no 'Suggested {kind}: \"...\"' in the suggested action")
            continue
        if kind != "header":
            continue
        words = header_words(wording)
        length.append(float(MIN_HEADER_WORDS <= words <= MAX_HEADER_WORDS))
        if not MIN_HEADER_WORDS <= words <= MAX_HEADER_WORDS:
            notes.append(f"{expected.id}: suggested header has {words} words: {wording!r}")
        original = section_number(header_text(lines[expected.line - 1]))
        if original is not None:
            kept = section_number(wording) == original
            number.append(float(kept))
            if not kept:
                notes.append(f"{expected.id}: suggested header {wording!r} drops the number {original!r}")
    values = {
        "suggestion_in_form": _fraction(in_form),
        "suggestion_header_length": _fraction(length),
        "suggestion_keeps_number": _fraction(number),
    }
    return values, " | ".join(notes) if notes else "all suggestion checks passed"


SUGGESTION_DESCRIPTIONS = {
    "suggestion_in_form": "Of the detected header and lead-sentence issues, share whose suggested action gives the wording as 'Suggested header: \"...\"' or 'Suggested lead: \"...\"'.",
    "suggestion_header_length": f"Of the suggested headers, share of {MIN_HEADER_WORDS} to {MAX_HEADER_WORDS} words, not counting a section number.",
    "suggestion_keeps_number": "Of the suggested headers for numbered headers ('3. Results', 'Chapter 4: Discussion'), share that keep the number unchanged. NaN when a sample has none.",
}

SUPPORTED_CRITERION = (
    "The suggested action proposes new wording for a report header or for a bold lead sentence, given after "
    "'Suggested header:' or 'Suggested lead:'. Judge only that wording, against the passage, which is the "
    "section the header opens or the paragraph the lead sentence opens and the only evidence there is. It is "
    "correct if everything the wording asserts is stated or directly shown in the passage: no causal claim where "
    "the passage reports only a comparison or an association (\"enrolled in more credits\" does not support "
    "\"passes raised enrollment\"), no impact or conclusion the passage does not state, no number the passage "
    "does not give, and, where the passage's findings are mixed or tentative, wording that says so rather than "
    "keeping only the favourable half. A header is 2 to 8 words, so it compresses: a close paraphrase of the "
    "passage's own terms (\"caseload demand\" for \"the caseload standard\", \"most families\" for a median) is "
    "supported, and so is a verb the passage itself uses or plainly implies. Judge overstatement the way the "
    "passage's author would, by whether they would object that the wording claims more than they showed. It is "
    "partially correct if it is supported but overstates one element, such as a stronger verb or a broader scope "
    "than the passage shows. It is incorrect if it asserts something the passage does not support or "
    "contradicts, or if there is no suggested wording."
)

POINT_CRITERION = (
    "The suggested action proposes new wording for a report header or for a bold lead sentence, given after "
    "'Suggested header:' or 'Suggested lead:'. It is correct if a reader who sees only that wording learns what "
    "the passage found or argues, its upshot, rather than only its topic. A header that states a finding in a few "
    "words (\"Court Staffing Falls Short of Caseload Demand\") is correct; one that renames the topic (\"Court "
    "Staffing Levels in 2023\") is not. A header of 2 to 8 words cannot carry every point of its passage, so it "
    "is correct when it states the main point, the one the rest of the passage supports, even if secondary "
    "details are left out. It is partially correct if it states a secondary point in place of the main one, or "
    "stays so general (\"Several Areas Need Attention\") that the reader still has to read the passage to learn "
    "what it found. It is incorrect if it is still a topic label, describes a different subject from the passage, "
    "or there is no suggested wording."
)

JUDGE_DESCRIPTIONS = {
    "suggestion_supported": "Graded per header or lead-sentence issue, with the section it heads: the suggested wording asserts nothing the section does not show, no causal claim, impact or conclusion beyond it (C=1, P=0.5, I=0).",
    "suggestion_states_point": "Graded per header or lead-sentence issue, with the section it heads: the suggested wording states the section's upshot rather than its topic (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(
        key="suggestion_supported", criterion=SUPPORTED_CRITERION, scope="expected", passage="section", applies_to=takes_suggestion
    ),
    JudgeCriterion(
        key="suggestion_states_point", criterion=POINT_CRITERION, scope="expected", passage="section", applies_to=takes_suggestion
    ),
]

SCORE_LABELS = {
    "suggestion_in_form": "In form",
    "suggestion_header_length": "Header length",
    "suggestion_keeps_number": "Keeps number",
    "suggestion_supported": "Supported",
    "suggestion_states_point": "States point",
}
