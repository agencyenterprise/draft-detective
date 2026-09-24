"""What Headers & Skimmability is judged on, beyond the generic layers.

The workflow proposes no edits: a new header or lead sentence is wording the
author chooses, so the skill puts it in the suggested action, in a fixed form
(``Suggested header: "..."``, ``Suggested lead: "..."``). The deterministic
checks read that wording back: the action begins with it, a header stays 2 to 8 words, and a
numbered header keeps its number. Markdown hashes and emphasis around the
wording are ignored. The judge grades the same wording against the section it
heads, which it sees in full (``passage="section"``).
"""

import re
from typing import Optional, Sequence

from evals_inspectai.common.issue_checks import fraction, hit_pairs
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

HEADER_TITLES = ("Vague Header", "Header Lacks Takeaway", "Header Does Not Match Content")
# The title of an optional header issue that any of the three header titles reports
# (matched as a whole word, so "Header" matches each of them).
ANY_HEADER_TITLE = "Header"
LEAD_TITLE = "Lead Sentence Lacks Takeaway"
MIN_HEADER_WORDS, MAX_HEADER_WORDS = 2, 8

# The suggested action begins with the wording, as the skill requires.
_SUGGESTION_RE = re.compile(r"^\s*Suggested (header|lead):\s*(?=[\"“])", re.I)
# "Chapter 3:", "Appendix B:", "Part II:", "3.", "2.1", "2.1.4" at the start of a header.
# The label is a number, one capital letter or a roman numeral, so "Part of the Gain"
# is not numbered; a bare number needs a dot, so "2024 Rate Increase" is not either.
_NUMBER_RE = re.compile(r"^\s*((?i:chapter|appendix|part)\s+(?:\d+|[A-Z]|[IVXLC]+)\b[:.]?|\d+(?:\.\d+)+\.?|\d+\.)\s+")


def is_header_issue(expected: ResolvedIssue) -> bool:
    return expected.title in (*HEADER_TITLES, ANY_HEADER_TITLE)


def takes_suggestion(expected: ResolvedIssue) -> bool:
    """Header and lead-sentence issues carry suggested wording; the others do not."""
    return is_header_issue(expected) or expected.title == LEAD_TITLE


def suggestion(action: Optional[str], kind: str) -> Optional[str]:
    """The wording after the ``Suggested <kind>:`` a suggested action begins with, or None."""
    match = _SUGGESTION_RE.match(action or "")
    if match is None or match.group(1).lower() != kind:
        return None
    quoted = _quoted(action or "", match.end())
    return header_text(quoted) if quoted else None


def _quoted(text: str, start: int) -> Optional[str]:
    """The text inside the quotation that opens at ``start``, keeping any quotation
    nested in it. A curly quote says which way it faces; a straight one opens when
    it follows a space and precedes a word, and closes otherwise."""
    depth = 0
    for i in range(start + 1, len(text)):
        char = text[i]
        opens = char == "“" or (char == '"' and text[i - 1].isspace() and text[i + 1 : i + 2].strip() != "")
        if opens:
            depth += 1
        elif char in '"”':
            if depth == 0:
                return text[start + 1 : i]
            depth -= 1
    return None


def header_text(line: str) -> str:
    """A markdown header line without its hashes or emphasis."""
    return line.lstrip("#").strip().strip("*").strip()


def section_number(header: str) -> Optional[str]:
    """A header's section number as written, delimiter and capitals included, since
    a suggestion keeps it exactly; only the spacing inside it is normalised."""
    match = _NUMBER_RE.match(header)
    return " ".join(match.group(1).split()) if match else None


def header_words(header: str) -> int:
    """Words in a header, not counting its section number."""
    return len(_NUMBER_RE.sub("", header, count=1).split())


SUGGESTION_KEYS = ("suggestion_in_form", "suggestion_header_length", "suggestion_keeps_number")


def _header_checks(expected: ResolvedIssue, wording: str, lines: list[str]) -> tuple[dict[str, float], list[str]]:
    """Length and number checks on one suggested header."""
    words = header_words(wording)
    fits = MIN_HEADER_WORDS <= words <= MAX_HEADER_WORDS
    scores = {"suggestion_header_length": float(fits)}
    notes = [] if fits else [f"{expected.id}: suggested header has {words} words: {wording!r}"]
    original = section_number(header_text(lines[expected.line - 1]))
    if original is not None:
        kept = section_number(wording) == original
        scores["suggestion_keeps_number"] = float(kept)
        if not kept:
            notes.append(f"{expected.id}: suggested header {wording!r} changes the number {original!r}")
    return scores, notes


def _suggestion_checks(expected: ResolvedIssue, issue: IssueItem, lines: list[str]) -> tuple[dict[str, float], list[str]]:
    """The suggestion checks on one detected header or lead-sentence issue."""
    kind = "header" if is_header_issue(expected) else "lead"
    wording = suggestion(issue.suggested_action, kind)
    if wording is None:
        return {"suggestion_in_form": 0.0}, [f"{expected.id}: the suggested action does not begin with 'Suggested {kind}: \"...\"'"]
    scores, notes = _header_checks(expected, wording, lines) if kind == "header" else ({}, [])
    return {"suggestion_in_form": 1.0, **scores}, notes


def suggestion_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """Over detected header and lead-sentence issues: the suggested wording is given in
    the skill's form, a suggested header is header-length, and a numbered header keeps
    its number. NaN where a sample has nothing of the kind."""
    lines = inventory.document.split("\n")
    values: dict[str, list[float]] = {key: [] for key in SUGGESTION_KEYS}
    notes: list[str] = []
    for expected, issue in hit_pairs(issues, inventory, one_to_one=True)[1]:
        if takes_suggestion(expected):
            scores, pair_notes = _suggestion_checks(expected, issue, lines)
            for key, value in scores.items():
                values[key].append(value)
            notes += pair_notes
    return {key: fraction(v) for key, v in values.items()}, " | ".join(notes) if notes else "all suggestion checks passed"


SUGGESTION_DESCRIPTIONS = {
    "suggestion_in_form": "Of the detected header and lead-sentence issues, share whose suggested action begins with the wording as 'Suggested header: \"...\"' or 'Suggested lead: \"...\"'.",
    "suggestion_header_length": f"Of the suggested headers, share of {MIN_HEADER_WORDS} to {MAX_HEADER_WORDS} words, not counting a section number.",
    "suggestion_keeps_number": "Of the suggested headers for numbered headers ('3. Results', 'Chapter 4: Discussion'), share that keep the number exactly as written, delimiter and capitals included. NaN when a sample has none.",
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
