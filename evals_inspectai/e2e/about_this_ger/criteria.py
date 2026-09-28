"""What About This (GER) is judged on, beyond the generic layers.

The workflow's two validators report from fixed title sets: six "Preface: <rule>
Missing" titles and "No preface section found" for the preface, and "Author Bio
Issue: <name>" and 'No "About the Authors" section found' for the author bios,
every one at severity medium. Deterministically, over every reported issue: the
title is one of those (an author title naming someone who appears in the
document), the severity is medium, and a "section not found" issue stands alone
in its validator, since the skills say not to evaluate the rules once the
section is missing. Per detected author issue: the title names the author of
the bio the issue is anchored on.

Graded, per detected issue, on the suggested action: for a preface issue,
against the whole report, it says what this report's preface should add and
invents nothing; for an author issue, against the bio, it says which element to
add or which sentence to cut for this author, names only failures the bio has,
and supplies no credentials the report does not state.
"""

import math
import re
from typing import Optional, Sequence

from evals_inspectai.common.issue_checks import hit_pairs
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue, normalize
from evals_inspectai.common.issue_judge import JudgeCriterion, section_text
from evals_inspectai.common.simple_deep_agent_types import IssueItem

PREFACE_RULES = (
    "Establishes Context",
    "Explains Objectives",
    "Identifies Audience",
    "Situates Within Literature",
    "States Contribution",
    "Defines Scope",
)
PREFACE_TITLES = tuple(f"Preface: {rule} Missing" for rule in PREFACE_RULES)
NO_PREFACE = "No preface section found"
NO_AUTHORS = 'No "About the Authors" section found'
# The stable part of "Author Bio Issue: {author_name}"; expected author issues carry it as their title.
AUTHOR_TITLE = "Author Bio Issue"

_PREFACE_SET = {normalize(t) for t in (*PREFACE_TITLES, NO_PREFACE)}
_AUTHORS_NOT_FOUND = normalize(NO_AUTHORS)
_AUTHOR_TITLE_RE = re.compile(r"^author bio issue:\s*(.+?)\s*$")
_HONORIFIC_RE = re.compile(r"^(?:dr|prof|professor|mr|mrs|ms)\.?\s+")
_NOT_FOUND = {normalize(NO_PREFACE), _AUTHORS_NOT_FOUND}


def author_name(title: str) -> Optional[str]:
    """The normalised author name an "Author Bio Issue: <name>" title carries, without a
    leading honorific (the skill substitutes the name as written, "Dr." or not); None for
    any other title."""
    match = _AUTHOR_TITLE_RE.match(normalize(title))
    return _HONORIFIC_RE.sub("", match.group(1)) if match else None


def validator_of(title: str) -> Optional[str]:
    """Which validator a title comes from, "preface" or "authors"; None for a title neither uses."""
    t = normalize(title)
    if t in _PREFACE_SET:
        return "preface"
    if t == _AUTHORS_NOT_FOUND or author_name(title) is not None:
        return "authors"
    return None


def _known(title: str, document: str) -> bool:
    """A fixed title, or an author title naming a full name (two words or more) found in the document."""
    if normalize(title) in _PREFACE_SET or normalize(title) == _AUTHORS_NOT_FOUND:
        return True
    name = author_name(title)
    return name is not None and len(name.split()) >= 2 and name in normalize(document)


def _not_found_alone(issues: Sequence[IssueItem]) -> tuple[float, list[str]]:
    """Share of reported "section not found" issues whose validator reported nothing else."""
    missing = [i for i in issues if normalize(i.title) in _NOT_FOUND]
    crowded = [
        i.title
        for i in missing
        if any(o is not i and validator_of(o.title) == validator_of(i.title) for o in issues)
    ]
    value = 1 - len(crowded) / len(missing) if missing else math.nan
    return value, [f"reported with rule issues from the same validator: {crowded}"] if crowded else []


def _author_named(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[float, list[str]]:
    """Of the detected author issues, share whose title names someone in the anchored bio."""
    checked: list[float] = []
    notes: list[str] = []
    for expected, issue in hit_pairs(issues, inventory, one_to_one=True)[1]:
        if expected.title != AUTHOR_TITLE or expected.line is None:
            continue
        name = author_name(issue.title)
        bio = normalize(section_text(inventory.document, expected.line))
        ok = name is not None and name in bio
        checked.append(float(ok))
        if not ok:
            notes.append(f"{expected.id}: {issue.title!r} does not name the author of that bio")
    return (sum(checked) / len(checked) if checked else math.nan), notes


def about_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``known_titles``, ``severity_medium`` and ``not_found_alone`` read every reported
    issue (NaN when there is none to read); ``author_named`` reads the detected author
    issues (NaN when none was detected)."""
    odd = [i.title for i in issues if not _known(i.title, inventory.document)]
    off = [f"{i.title} ({i.severity})" for i in issues if i.severity != "medium"]
    alone, alone_notes = _not_found_alone(issues)
    named, named_notes = _author_named(issues, inventory)
    values = {
        "known_titles": 1 - len(odd) / len(issues) if issues else math.nan,
        "severity_medium": 1 - len(off) / len(issues) if issues else math.nan,
        "not_found_alone": alone,
        "author_named": named,
    }
    notes = [f"titles outside the skills' sets: {odd}"] if odd else []
    notes += [f"severity not medium: {off}"] if off else []
    notes += alone_notes + named_notes
    return values, " | ".join(notes) if notes else "titles known, severities medium, authors named"


PREFACE_CRITERION = (
    "The reviewer reported that a research report's preface (its About This Report, Preface, Introduction or "
    "similar opening section) lacks one of six required elements: why the work was undertaken, what it aims to "
    "achieve, who it is for, how it relates to prior research, its novel contribution, or what it does and does "
    "not cover; or that the report has no preface at all. The full report is shown. Grade whether the suggested "
    "action tells the author what this report's preface should add, drawing on the report itself: for a missing "
    "audience, the readers the report's subject and findings point to; for missing objectives, the aims its "
    "methods and findings reveal; for missing scope, the boundaries its analysis actually has (cases, period, "
    "what it leaves out); for a missing contribution, what its data, method or findings add; for missing context, "
    "the problem the report addresses; for missing literature, prior work the report names elsewhere or, where it "
    "names none, a request that the author situate the study, without naming works for them; for a missing "
    "preface, a preface covering the six elements for this report. Advice that could be pasted onto any report "
    "(\"add a sentence identifying the intended audience\") is incorrect. An action that invents a citation, a "
    "funder, a finding or a fact the report does not contain is incorrect."
)

BIO_CRITERION = (
    "The reviewer reported that an author biography in a research report fails one or more of four rules: it has "
    "exactly three sentences (abbreviations with periods, such as Ph.D., M.A., Dr. or e.g., do not end a "
    "sentence); it states the author's current position and institutional affiliation; it describes the author's "
    "research focus; it names the author's highest academic degree. Or the reviewer reported that the report has "
    "no author biography section. The passage shown is the biography, or the full report for a missing section. "
    "Grade whether the suggested action tells the author concretely how to fix this biography for this author: "
    "which element to add (the institution, the research area, the degree) or which sentence to cut or merge to "
    "reach three sentences; and whether every failure it names is one this biography actually has (an action "
    "asking to add an element the biography already states is incorrect). Grade the action only on the failures "
    "it names: the reviewer may report each failed rule of a biography as a separate issue, so if the biography "
    "also fails a rule this action does not mention, ignore that failure and do not lower the grade for it. An "
    "action that explicitly asks for a new sentence in a biography that already has three, without saying what to "
    "cut or merge, breaks the sentence rule and is only partly correct; asking to add an element to the biography "
    "without saying it must be a new sentence is fine. It must not supply a degree, "
    "institution, position or research area the report does not state; asking the author to supply it is "
    "correct. For a missing section, asking for a three-sentence biography per author with the four elements is "
    "correct, naming authors only if the report names them. An action that only restates the rules (\"ensure the "
    "bio meets the requirements\") is incorrect."
)


def is_preface_issue(expected: ResolvedIssue) -> bool:
    return expected.title is not None and validator_of(expected.title) == "preface"


def is_author_issue(expected: ResolvedIssue) -> bool:
    return expected.title in (AUTHOR_TITLE, NO_AUTHORS)


JUDGE_CRITERIA = [
    JudgeCriterion(
        key="preface_action",
        criterion=PREFACE_CRITERION,
        scope="expected",
        passage="document",
        applies_to=is_preface_issue,
    ),
    # A missing author section has no anchor, so the grader is shown the whole report for it.
    JudgeCriterion(
        key="bio_action",
        criterion=BIO_CRITERION,
        scope="expected",
        passage="section",
        applies_to=is_author_issue,
    ),
]

JUDGE_DESCRIPTIONS = {
    "preface_action": "Graded per detected preface issue against the whole report: the suggested action says what this report's preface should add, drawn from the report, inventing nothing (C=1, P=0.5, I=0).",
    "bio_action": "Graded per detected author issue against the bio (the whole report for a missing section): the suggested action says which element to add or which sentence to cut for this author, names only real failures and supplies no credentials (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "known_titles": "Share of reported issues titled as the skills name them: a fixed preface title, a 'section not found' title, or 'Author Bio Issue: <name>' with a full name found in the document; NaN when nothing was reported.",
    "severity_medium": "Share of reported issues, matched or not, with severity medium as both skills require; NaN when nothing was reported.",
    "not_found_alone": "Share of reported 'section not found' issues with no other issue from the same validator, since the rules are not evaluated when the section is missing; NaN when none was reported.",
    "author_named": "Of the detected author issues, share whose title names the author of the bio the expected issue is anchored on; NaN when none was detected.",
}

SCORE_LABELS = {
    "known_titles": "Known titles",
    "severity_medium": "All medium",
    "not_found_alone": "Not-found alone",
    "author_named": "Author named",
    "preface_action": "Preface action",
    "bio_action": "Bio action",
}
