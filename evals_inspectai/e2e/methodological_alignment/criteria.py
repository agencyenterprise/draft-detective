"""What Methodological Alignment is judged on.

The skill reports every missing standard component and methodological risk,
anchored at the passage the choice is described in, or, for an omission, the
passage it affects. So a report on a line with a planted risk may be about
another gap on that passage, a report elsewhere is not a false positive, and a
line cannot tell a criticism of a sound choice from one of its neighbour. The
planted risks are therefore scored in two ways: deterministically, whether
some issue sits on the plant's line (``recall``, ``anchor_in_range``) and a
high-severity plant is not reported as low; and by a grader, which reads every
issue on the plant's line against the labeller's account of the risk
(``gap_identified``, the best grade among them, 0 when none is there) and the
suggested action of the issue that named it (``action_repairs``). Sound choices
are graded one by one against every issue the run reported
(``sound_choices_respected``).

The report checks are the skill's contract for the deliverable: its five
sections, web sources cited as links, and no informational issue.
"""

import re
from typing import Sequence

from evals_inspectai.common.issue_inventory import Decoy, ResolvedIssue
from evals_inspectai.common.issue_judge import READS_LABELS, REFERENCE_LABEL, issue_prompt_from, section_text
from evals_inspectai.common.simple_deep_agent_types import IssueItem

# Section headings the skill's report template requires, matched as headings of any level.
REQUIRED_SECTIONS = (
    "Extracted Methodology",
    "Field Methods Overview",
    "Alignment with Field Practice",
    "Methodological Rigor and Risks",
    "Suggestions for Improvements",
)
# The skill demands markdown links for every claim about field practice.
_CITATION_LINK = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")
_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _has_heading(report: str, title: str) -> bool:
    return re.search(rf"^#+\s*{re.escape(title)}\b", report, re.M | re.I) is not None


def report_scores(report: str, issues: Sequence[IssueItem]) -> tuple[dict[str, float], str]:
    """``report_sections``: share of the five required sections present. ``report_cites_links``:
    1 if the report cites a web source as a markdown link. ``no_informational``: share of issues
    whose severity is not ``none`` (NaN when nothing was reported)."""
    missing = [t for t in REQUIRED_SECTIONS if not _has_heading(report, t)]
    informational = [i.title for i in issues if i.severity.lower() == "none"]
    values = {
        "report_sections": 1 - len(missing) / len(REQUIRED_SECTIONS),
        "report_cites_links": float(bool(_CITATION_LINK.search(report))),
        "no_informational": 1 - len(informational) / len(issues) if issues else float("nan"),
    }
    notes = [f"missing sections: {missing}"] if missing else []
    notes += ["no markdown link to a web source"] if not values["report_cites_links"] else []
    notes += [f"informational issues: {informational}"] if informational else []
    return values, " | ".join(notes) if notes else "report contract met"


def severity_fits(expected: ResolvedIssue, issues: Sequence[IssueItem]) -> bool:
    """Whether some issue on the plant's line has a severity within one step of the
    labelled one, so a plant labelled high is not reported only as low or none."""
    assert expected.severity is not None
    target = _SEVERITY_RANK[expected.severity]
    return any(abs(target - _SEVERITY_RANK.get(i.severity.lower(), 0)) <= 1 for i in issues)


GAP_CRITERION = (
    "A reviewer compared a paper's methodology with standard practice in its field and reported a methodological "
    "gap or risk. The labeller has planted a specific risk in this passage and described what the field does "
    "instead. The reviewer may report other gaps on the same passage; grade only whether this issue identifies "
    "the planted risk: the same design problem and why it threatens the result, in any words. It is correct if it "
    "names that problem, even alongside others. It is partially correct if it touches the problem but its main "
    "point is a different or vaguer weakness. It is incorrect if it is about a different gap, or only says the "
    "passage lacks detail."
)

REPAIR_CRITERION = (
    "A reviewer reported a methodological risk in a paper, and the passage it sits in is shown with the "
    "labeller's account of what the field does instead. Grade whether the suggested action tells the authors "
    "concretely how to repair this risk: the design change, analysis or check the field uses, or, when the data "
    "cannot be changed, how to bound the claims. Generic advice (\"improve rigor\", \"follow best practice\", "
    "\"add more detail\") is incorrect."
)

DECOY_CRITERION = (
    "A reviewer compared a paper's methodology with standard practice in its field and reported the issues "
    "listed. The labeller marked one design choice in the paper as sound, for the reason given. Grade whether the "
    "reviewer left this choice alone. It is correct if no issue criticises this choice itself as missing, weak, "
    "or inappropriate (issues about other aspects of the same passage, or that build on this choice, are fine). "
    "It is partially correct if an issue questions it only in passing, or asks only for more detail about it. It "
    "is incorrect if an issue reports this choice as a gap or risk."
)


def gap_prompt(criterion: str, expected: ResolvedIssue, issue: IssueItem, document: str, reads: str) -> str:
    """The prompt grading one issue on a plant's line against the labeller's account of the plant."""
    assert expected.line is not None and expected.anchor is not None
    if reads == "suggested_action":
        read = issue.suggested_action or ""
    else:
        read = "\n\n".join(part for part in (issue.title, issue.description, issue.long_description or "") if part.strip())
    return issue_prompt_from(
        criterion,
        [
            ("Passage the issue is about", section_text(document, expected.line)),
            ("Text the planted risk is anchored to", expected.anchor),
            (REFERENCE_LABEL, expected.rationale or ""),
            (READS_LABELS["suggested_action" if reads == "suggested_action" else "analysis"], read),
        ],
    )


def _issue_summary(issue: IssueItem) -> str:
    """One reported issue in full, since its criticism of a choice may sit in any field."""
    parts = [f"- {issue.title} (lines {issue.start_line}-{issue.end_line}): {issue.description}"]
    parts += [f"  Analysis: {issue.long_description}"] if (issue.long_description or "").strip() else []
    parts += [f"  Suggested action: {issue.suggested_action}"] if (issue.suggested_action or "").strip() else []
    return "\n".join(parts)


def decoy_prompt(decoy: Decoy, issues: Sequence[IssueItem], document: str) -> str:
    """The prompt grading whether any reported issue criticises one sound choice."""
    return issue_prompt_from(
        DECOY_CRITERION,
        [
            ("Paper under review", document),
            ("Design choice marked sound", decoy.anchor),
            ("Labeller's reason it is sound", decoy.rationale or decoy.reason),
            ("Reviewer's issues", "\n".join(_issue_summary(i) for i in issues) or "(none)"),
        ],
    )


JUDGED_KEYS = ("gap_identified", "action_repairs", "sound_choices_respected")

OWN_DESCRIPTIONS = {
    "report_sections": "Share of the skill's five report sections present as headings.",
    "report_cites_links": "1 if the report cites at least one web source as a markdown link.",
    "no_informational": "Share of reported issues whose severity is not 'none'. NaN when nothing was reported.",
}
PLANT_DESCRIPTIONS = {
    "recall": "Share of planted risks with at least one reported issue quoting the anchor or bracketing its line. Location only: gap_identified says whether that issue names the risk.",
    "anchor_in_range": "Of the covered planted risks, share whose line lies inside the matched issue's range.",
    "severity_fits": "Of the covered planted risks labelled high, share with an issue on their line reported as high or medium.",
}
JUDGE_DESCRIPTIONS = {
    "gap_identified": "Graded per planted risk: the best grade among the issues on its line, read against the labeller's account of the risk; 0 when no issue is there (C=1, P=0.5, I=0).",
    "action_repairs": "Graded per identified planted risk, on the issue that named it: the suggested action says concretely how to repair the risk (C=1, P=0.5, I=0).",
    "sound_choices_respected": "Graded per sound design choice against every reported issue: no issue criticises the choice itself (C=1, P=0.5, I=0).",
}
SCORE_LABELS = {
    "report_sections": "Sections",
    "report_cites_links": "Links",
    "no_informational": "No 'none'",
    "recall": "Recall",
    "anchor_in_range": "Lines",
    "severity_fits": "Severity",
    "gap_identified": "Gap identified",
    "action_repairs": "Action repairs",
    "sound_choices_respected": "Sound left alone",
}
