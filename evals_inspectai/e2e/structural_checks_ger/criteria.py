"""What Structural Checks (GER) is judged on, beyond the generic layers.

The rules come from the skill itself (``skills/structural-checks-ger/SKILL.md``),
not from a copy here: each criterion shows the grader the part of the skill the
issue falls under, then asks one grading question about the suggested action.
Editing the skill's rules therefore changes what the grader holds the run to,
and nothing in this suite can drift from them.

An expected issue's part is read from its title: "Missing Section: <name>" for
the required sections, "Preface: <element> Missing" for About This, and the
stable "Author Bio Issue" for About the Authors. Every detected issue is graded
against the whole report, except an author issue, graded against its bio.
"""

import re
from pathlib import Path

from evals_inspectai.common.issue_inventory import ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion

SKILL_FILE = Path(__file__).parents[3] / "skills/structural-checks-ger/SKILL.md"
# The stable part of "Author Bio Issue: {author_name}"; expected author issues carry it as their title.
AUTHOR_TITLE = "Author Bio Issue"


def skill_part(number: int, skill: str | None = None) -> str:
    """The skill's ``## <number> — <name>`` section, heading included, up to the next ``## `` heading."""
    text = SKILL_FILE.read_text() if skill is None else skill
    match = re.search(rf"^## {number} — .*?(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        raise ValueError(f"{SKILL_FILE} has no '## {number} — ' section")
    return match.group(0).strip()


def _criterion(part: int, question: str) -> str:
    return (
        "A reviewer checked a research report against the rules below, taken from its instructions, and "
        f"reported the issue shown.\n\n<rules>\n{skill_part(part)}\n</rules>\n\n{question}"
    )


SECTION_SPECIFIC = _criterion(
    1,
    "The reviewer reported that the report lacks one of these sections, and the full report is shown. Grade "
    "whether the suggested action tells the author what this report's missing section should contain, drawing "
    "on the report itself (the data and analysis it relies on, the findings it states elsewhere, the works it "
    "cites, the material the body says an appendix holds, the authors it names). Where the report gives nothing "
    "to draw on, asking the author for that information is correct. Advice that could be pasted onto any report "
    '("add a Methods section describing your methodology") is incorrect.',
)
SECTION_GROUNDED = _criterion(
    1,
    "The reviewer reported that the report lacks one of these sections, and the full report is shown. Grade "
    "whether everything specific the suggested action proposes for the section (data sources, methods, "
    "findings, funders, cited works, appendix contents, author credentials) appears in or follows directly from "
    "the report. An action that invents any of these is incorrect. An action that proposes nothing specific, or "
    "asks the author to supply what the report does not say, is correct.",
)
PREFACE_ACTION = _criterion(
    2,
    "The reviewer reported that the report's preface lacks one of these elements, and the full report is "
    "shown. Grade the suggested action against what the rules ask of it: what this report's preface should add, "
    "drawn from the rest of the report rather than advice that would fit any report. For a missing place in "
    "the literature, prior work the report names elsewhere or, where it names none, a request that the author "
    "situate the study, without naming works for them. An action that invents a citation, a funder, a finding "
    "or a fact the report does not contain is incorrect.",
)
BIO_ACTION = _criterion(
    3,
    "The reviewer reported that one author's biography fails one or more of these rules, and the biography is "
    "shown. Grade the suggested action against what the rules ask of it: for this author, which element to add "
    "or which sentence to cut or merge to reach three sentences. It must address every rule the biography fails "
    "(leaving one unaddressed is only partly correct) and name no failure the biography does not have (asking "
    "for an element it already states is incorrect). Asking for a new sentence in a biography that already has "
    "three, without saying what to cut or merge, is only partly correct. Supplying a degree, institution, "
    "position or research area the report does not state is incorrect; asking the author for it is correct.",
)


def part_of(expected: ResolvedIssue) -> str | None:
    """Which part of the skill an expected issue falls under, read from its title."""
    title = expected.title or ""
    if title.startswith("Missing Section:"):
        return "sections"
    if title.startswith("Preface:"):
        return "preface"
    if title == AUTHOR_TITLE:
        return "authors"
    return None


JUDGE_CRITERIA = [
    JudgeCriterion(
        key="section_action_specific",
        criterion=SECTION_SPECIFIC,
        scope="expected",
        passage="document",
        applies_to=lambda e: part_of(e) == "sections",
    ),
    JudgeCriterion(
        key="section_action_grounded",
        criterion=SECTION_GROUNDED,
        scope="expected",
        passage="document",
        applies_to=lambda e: part_of(e) == "sections",
    ),
    JudgeCriterion(
        key="preface_action",
        criterion=PREFACE_ACTION,
        scope="expected",
        passage="document",
        applies_to=lambda e: part_of(e) == "preface",
    ),
    JudgeCriterion(
        key="bio_action",
        criterion=BIO_ACTION,
        scope="expected",
        passage="section",
        applies_to=lambda e: part_of(e) == "authors",
    ),
]

JUDGE_DESCRIPTIONS = {
    "section_action_specific": "Graded per detected missing-section issue against the whole report, with the skill's required-sections rules: the suggested action says what this report's missing section should contain (C=1, P=0.5, I=0).",
    "section_action_grounded": "Graded per detected missing-section issue against the whole report, with the skill's required-sections rules: anything specific the suggested action proposes comes from the report (C=1, P=0.5, I=0).",
    "preface_action": "Graded per detected preface issue against the whole report, with the skill's About This rules: the suggested action says what this report's preface should add, inventing nothing (C=1, P=0.5, I=0).",
    "bio_action": "Graded per detected author issue against the bio, with the skill's About the Authors rules: the suggested action addresses every rule the bio fails and only those, and supplies no credentials (C=1, P=0.5, I=0).",
}

SCORE_LABELS = {
    "section_action_specific": "Section action specific",
    "section_action_grounded": "Section action grounded",
    "preface_action": "Preface action",
    "bio_action": "Bio action",
}
