"""What Figures & Tables Check is judged on, beyond the generic layers.

The skill fixes the shape of every title: one of four rule prefixes followed by
the element's label ("Figure/Table Missing Title: Figure 3"). The generic title
check only matches the rule part, so two deterministic checks read the rest:
every reported title uses one of the four prefixes with the placeholder filled
in (a variant would not group with the others in the app), and a detected issue
about one element names that element's label in its title, the label its anchor
carries ("Fig. 2" and "Figure 2" are the same label). Graded, per detected
issue against the whole report: the suggested action is concrete about this
element, and anything specific it proposes comes from the report.

The judge is shown the whole report rather than the anchor's section: an
element issue is anchored on a caption or a citing sentence, whose section is
that one paragraph, while judging a proposed caption or callout needs the
element's content and the body text around it.
"""

import math
import re
from typing import Optional, Sequence

from evals_inspectai.common.issue_checks import fraction, hit_pairs
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue, normalize
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

MISSING_TITLE = "Figure/Table Missing Title"
NUMBERING = "Inconsistent Numbering"
UNREFERENCED = "Unreferenced Figure/Table"
MISSING_ELEMENT = "Missing Figure/Table"
TITLE_PREFIXES = (MISSING_TITLE, NUMBERING, UNREFERENCED, MISSING_ELEMENT)
# The rules whose title placeholder is one element's label; a numbering title is a free description.
ELEMENT_RULES = (MISSING_TITLE, UNREFERENCED, MISSING_ELEMENT)

# "Figure 2", "Fig. 2", "FIGURE 2.1", "Table A.1", "Table S1", "Figure S.1": the kind, then
# an optional letter prefix (appendix or supplementary) and a dotted number.
_LABEL_RE = re.compile(r"\b(fig(?:ure)?\.?|table)\s+([a-z]?\.?\d+(?:\.\d+)*)\b", re.I)


def label(text: str) -> Optional[tuple[str, str]]:
    """The first figure or table label in ``text`` as (kind, number), or None.

    "Fig." and "Figure" are one kind, case is ignored, and a dot between a letter
    prefix and its number is dropped, so "Table S.1" and "Table S1" are one label."""
    match = _LABEL_RE.search(text)
    if match is None:
        return None
    kind = "table" if match.group(1).lower() == "table" else "figure"
    number = re.sub(r"^([A-Z])\.", r"\1", match.group(2).upper())
    return kind, number


def title_parts(title: str) -> Optional[tuple[str, str]]:
    """The skill's rule prefix a title begins with and its placeholder, or None when
    the title does not begin with one of the four prefixes and a colon."""
    for prefix in TITLE_PREFIXES:
        head = normalize(prefix) + ":"
        if normalize(title).startswith(head):
            return prefix, title.split(":", 1)[1].strip()
    return None


def _known(title: str) -> bool:
    """One of the four prefixes, with the placeholder filled in rather than left as "[label]"."""
    parts = title_parts(title)
    return parts is not None and parts[1] != "" and not parts[1].startswith("[")


def _element_label(expected: ResolvedIssue) -> Optional[tuple[str, str]]:
    """The label an expected element issue is about, read from its anchor; None for a
    numbering issue, an unanchored issue or an anchor that carries no label."""
    if expected.title not in ELEMENT_RULES or expected.anchor is None:
        return None
    return label(expected.anchor)


def _label_check(expected: ResolvedIssue, issue: IssueItem) -> Optional[tuple[float, str]]:
    """Whether the reported title names the expected element's label; None when there is none to compare."""
    wanted = _element_label(expected)
    if wanted is None:
        return None
    parts = title_parts(issue.title)
    named = label(parts[1]) if parts is not None else None
    if named == wanted:
        return 1.0, ""
    return 0.0, f"{expected.id}: title {issue.title!r} does not name {' '.join(wanted)}"


def title_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``known_titles``: share of reported issues whose title is one of the skill's four
    prefixes with the placeholder filled in; NaN when nothing was reported.
    ``title_names_element``: of the detected expected issues about one labelled
    element, share whose reported title names that label; NaN when there are none."""
    odd = [i.title for i in issues if not _known(i.title)]
    checks = [
        result
        for expected, issue in hit_pairs(issues, inventory, one_to_one=True)[1]
        if (result := _label_check(expected, issue)) is not None
    ]
    values = {
        "known_titles": 1 - len(odd) / len(issues) if issues else math.nan,
        "title_names_element": fraction([value for value, _ in checks]),
    }
    notes = [f"titles outside the skill's set: {odd}"] if odd else []
    notes += [note for value, note in checks if value < 1.0]
    return values, " | ".join(notes) if notes else "titles known; labels match"


_CONTEXT = (
    "The reviewer flagged a figure or table problem in a research report (a figure or table with no title or "
    "caption, one never referred to in the body text, a body reference to a figure or table the report does not "
    "contain, or inconsistent numbering), and the full report is shown. Take the flagged problem as given: "
    "whether it is real is scored separately, and under the review's rules a mention of a figure or table inside "
    "another figure's or table's caption is not a body-text reference. Grade only the suggested action. Line "
    "numbers in the action refer to the report's lines, which are not shown: do not check them, but \"the "
    "reference on line N\" still names that reference. "
)

CONCRETE_CRITERION = _CONTEXT + (
    "The reporting conventions ask a suggested action to name the element, point to where the fix goes and "
    "state the change, in terms specific to this report; they leave new prose to the author. Grade whether the "
    "action does that: for a missing title, it says what the caption should identify, named from the element's "
    "own content or the sentence introducing it (\"a caption identifying year-over-year growth rates by product "
    "line\" is enough; exact caption wording is not required); for an unreferenced element, it names the section "
    "or sentence where the callout belongs, one that discusses the element's content; for a missing element, it "
    "names the unresolved reference and says to supply the element or correct the reference; for numbering, it "
    "says which labels change to which numbers and, where a renumbered element is cited in the body, that those "
    "citations change too. Offering a choice between concrete fixes is correct. Advice that fits any report "
    "(\"add a descriptive caption\", \"reference the table in the text\", \"fix the numbering\") is incorrect. An "
    "action that is concrete about part of the fix and generic about the rest (a caption described only as "
    "\"descriptive\", a renumbering that leaves the citing references unmentioned) is partially correct."
)

GROUNDED_CRITERION = _CONTEXT + (
    "Grade whether everything specific the suggested action proposes follows from the report: a proposed "
    "caption describes only what the element shows (its variables, groups, units and period) or what the text "
    "introducing it says; a proposed callout sits in a section that discusses the element's content; a proposed "
    "number fits the report's numbering scheme and does not collide with a number another figure or table "
    "already uses unless the action renumbers that one too; and a missing element is described only as the "
    "citing text describes it (offering to add the element a numbering gap skips, without describing it, is "
    "fine). An action that proposes a caption with content, units or a period the element does not show, a "
    "finding the report does not state, or a number that collides with an existing one, is incorrect. An action "
    "that proposes nothing specific, or leaves the wording to the author, is correct."
)

JUDGE_CRITERIA = [
    JudgeCriterion(key="action_concrete", criterion=CONCRETE_CRITERION, scope="expected", passage="document"),
    JudgeCriterion(key="action_grounded", criterion=GROUNDED_CRITERION, scope="expected", passage="document"),
]

JUDGE_DESCRIPTIONS = {
    "action_concrete": "Graded per detected issue against the whole report: the suggested action names the element, where the fix goes and the change (what the caption should identify, which section takes the callout, which numbers and references change), not advice that fits any report (C=1, P=0.5, I=0).",
    "action_grounded": "Graded per detected issue against the whole report: any caption, callout location or number the action proposes follows from the report and collides with nothing (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "known_titles": "Share of reported issues titled with one of the skill's four prefixes ('Figure/Table Missing Title:', 'Inconsistent Numbering:', 'Unreferenced Figure/Table:', 'Missing Figure/Table:') and the placeholder filled in; NaN when nothing was reported.",
    "title_names_element": "Of the detected issues about one labelled element (missing title, unreferenced, missing), share whose title names the label the expected anchor carries ('Fig. 2' and 'Figure 2' match); NaN when there are none.",
}

SCORE_LABELS = {
    "known_titles": "Known titles",
    "title_names_element": "Label in title",
    "action_concrete": "Concrete action",
    "action_grounded": "Grounded action",
}
