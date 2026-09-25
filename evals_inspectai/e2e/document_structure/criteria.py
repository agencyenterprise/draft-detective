"""What Document Structure is judged on, beyond the generic layers.

Every issue this check reports names a section the document lacks, so beyond
detection what it gets right or wrong is in two places. Deterministically: its
titles come from the skill's fixed set (a variant title would not group with
the others in the app), and an appendix issue points the author to the body
sentence that refers to the appendix (quoting it, naming its line, or placing
the issue on it), since that sentence is the only evidence the appendix is
required at all. Graded, per detected issue against the whole report: the
suggested action says what this report's missing section should contain, and
anything specific it proposes comes from the report itself.
"""

import math
import re
from typing import Sequence

from evals_inspectai.common.issue_inventory import ResolvedInventory, normalize
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

SECTIONS = ("About This", "Acknowledgements", "Methods", "Results", "Conclusion", "References", "Appendix")
TITLES = tuple(f"Missing Section: {name}" for name in SECTIONS)
APPENDIX_TITLE = "Missing Section: Appendix"

_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_APPENDIX_RE = re.compile(r"\bappendix\b", re.I)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
# Consecutive words an issue must share with the sentence to count as quoting it.
QUOTE_WORDS = 4


def _issue_text(issue: IssueItem) -> str:
    return normalize(" ".join([issue.description, issue.long_description or "", issue.suggested_action or ""]))


def appendix_mentions(document: str) -> list[tuple[int, str]]:
    """The body sentences that mention an appendix, with their 1-indexed line: headings
    are left out, since an appendix heading is the appendix itself, not a reference to it."""
    return [
        (number, sentence)
        for number, line in enumerate(document.split("\n"), 1)
        if not _HEADING_RE.match(line)
        for sentence in _SENTENCE_RE.split(line)
        if _APPENDIX_RE.search(sentence)
    ]


def _quotes(text: str, sentence: str) -> bool:
    words = normalize(sentence).split()
    runs = {" ".join(words[i : i + QUOTE_WORDS]) for i in range(len(words) - QUOTE_WORDS + 1)}
    return any(run in text for run in runs)


def _cites(issue: IssueItem, mentions: Sequence[tuple[int, str]]) -> bool:
    """Whether the issue points to a sentence referring to the appendix: it quotes it,
    names its line ("line 19"), or its line range brackets that line."""
    text = _issue_text(issue)
    return any(
        _quotes(text, sentence)
        or re.search(rf"\blines? {number}\b", text) is not None
        or issue.start_line <= number <= issue.end_line
        for number, sentence in mentions
    )


def structure_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``known_titles``: share of reported issues titled exactly as the skill names a
    missing section; NaN when nothing was reported. ``appendix_reference_cited``:
    share of reported appendix issues that point to a body sentence mentioning the
    appendix (see ``_cites``); NaN when none was reported."""
    known = {normalize(t) for t in TITLES}
    odd = [i.title for i in issues if normalize(i.title) not in known]
    appendix = [i for i in issues if normalize(i.title) == normalize(APPENDIX_TITLE)]
    mentions = appendix_mentions(inventory.document)
    uncited = [i for i in appendix if not _cites(i, mentions)]
    values = {
        "known_titles": 1 - len(odd) / len(issues) if issues else math.nan,
        "appendix_reference_cited": 1 - len(uncited) / len(appendix) if appendix else math.nan,
    }
    notes = [f"titles outside the skill's set: {odd}"] if odd else []
    notes += [f"{len(uncited)}/{len(appendix)} appendix issues do not point to the sentence that refers to it"] if uncited else []
    return values, " | ".join(notes) if notes else "titles known; appendix references cited"


SPECIFIC_CRITERION = (
    "The reviewer reported that a research report is missing a required section (About This, "
    "Acknowledgements, Methods, Results, Conclusion, References, or an Appendix the body refers to), and the "
    "full report is shown. Grade whether the suggested action tells the author what this report's missing "
    "section should contain, drawing on the report itself: for Methods, the data and analysis the report "
    "actually relies on; for Results, the findings the report states or implies elsewhere; for References, "
    "the works the text cites; for an Appendix, the material the body says the appendix holds; for About "
    "This, the purpose and audience the report's content suggests; for Conclusion, the implications of this "
    "report's findings. Where the report gives nothing to draw on (no funder or contributor is named anywhere, "
    "say, for Acknowledgements), asking the author for that information is correct. Advice that could be "
    "pasted onto any report (\"add a Methods section describing your methodology\") is incorrect."
)

GROUNDED_CRITERION = (
    "The reviewer reported that a research report is missing a required section, and the full report is "
    "shown. Grade whether everything specific the suggested action proposes for the section (data sources, "
    "methods, findings, funders, contributors, cited works, appendix contents) appears in or follows directly "
    "from the report. An action that invents a funder, a method, a finding or a citation the report does not "
    "contain is incorrect. An action that proposes nothing specific, or asks the author to supply what the "
    "report does not say, is correct."
)

JUDGE_CRITERIA = [
    JudgeCriterion(key="action_specific", criterion=SPECIFIC_CRITERION, scope="expected", passage="document"),
    JudgeCriterion(key="action_grounded", criterion=GROUNDED_CRITERION, scope="expected", passage="document"),
]

JUDGE_DESCRIPTIONS = {
    "action_specific": "Graded per detected issue against the whole report: the suggested action says what this report's missing section should contain, not advice that fits any report (C=1, P=0.5, I=0).",
    "action_grounded": "Graded per detected issue against the whole report: anything specific the suggested action proposes comes from the report (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "known_titles": "Share of reported issues titled exactly as the skill names a missing section; NaN when nothing was reported.",
    "appendix_reference_cited": "Share of reported 'Missing Section: Appendix' issues that point to the body sentence referring to the appendix (quote it, name its line, or sit on it); NaN when none was reported.",
}

SCORE_LABELS = {
    "known_titles": "Known titles",
    "appendix_reference_cited": "Appendix ref cited",
    "action_specific": "Specific action",
    "action_grounded": "Grounded action",
}
