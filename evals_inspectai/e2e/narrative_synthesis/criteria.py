"""What Narrative & Synthesis is judged on, beyond the generic layers.

The check proposes no edits, so what it gets right or wrong beyond detection
is in its suggested actions. Two graded criteria read them against the passage
the issue is about: the action is specific to that passage, and any takeaway it
offers for a data dump stays within what the data show. One deterministic check
reads every reported issue: it explains the problem in plain terms, never by
pointing at a rule or guideline.
"""

import math
import re
from typing import Sequence

from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

DATA_TITLE = "Data Without Synthesis"

# Phrases that make the review process visible to the author: the editing rules
# or guidelines, a style guide, or the source of the rules by name. A bare
# "guidelines" is left alone, since reports discuss guidelines as content.
RULE_REFERENCE_RE = re.compile(
    r"\b(?:(?:editing|writing|style) (?:rules?|guidelines?)|per the (?:rules?|guidelines?)"
    r"|the (?:rules?|guidelines?) (?:say|ask|require|states?)|style guide|writing for impact|EEI)\b",
    re.I,
)


def _issue_text(issue: IssueItem) -> str:
    return " ".join([issue.title, issue.description, issue.long_description or "", issue.suggested_action or ""])


def rule_reference_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``no_rule_reference``: share of reported issues whose text names no rule or
    guideline. NaN when the run reported nothing."""
    if not issues:
        return {"no_rule_reference": math.nan}, "nothing reported"
    cited = [i.title for i in issues if RULE_REFERENCE_RE.search(_issue_text(i))]
    value = 1 - len(cited) / len(issues)
    return {"no_rule_reference": value}, (f"cites a rule: {cited}" if cited else "no issue cites a rule")


SPECIFIC_CRITERION = (
    "The reviewer flagged a problem with how a research report builds its argument (data reported without "
    "its takeaway, sections out of logical order, a framing question the report never answers, or a point "
    "restated from an earlier section), and the passage shown is where the issue is anchored. Grade whether "
    "the suggested action tells the author concretely what to do about this passage, in terms that could not "
    "be pasted onto a different report: for a data dump, the comparison or pattern the figures appear to show "
    "or the specific question the author must answer to state a takeaway; for order, which section should "
    "move and where; for a missing framing question, what the answer should cover given the report's topic; "
    "for a restated point, which earlier section already made it and whether to cut it or refer back. Generic "
    "advice that fits any passage (\"add interpretation\", \"consider restructuring\", \"explain why this "
    "matters\") is incorrect. An action that is specific but also asks the author to decide between readings "
    "is correct."
)

WITHIN_EVIDENCE_CRITERION = (
    "The reviewer flagged the passage as data reported without a takeaway, and the suggested action may "
    "propose a takeaway or a pattern the author could state. Grade whether everything the action proposes is "
    "supported by the figures or facts in the passage shown: it does not claim causes, effects, impacts, "
    "trends or comparisons the passage's data do not establish, and it does not add numbers the passage does "
    "not contain. Proposing a comparison the numbers plainly show (one group higher than another, a rise "
    "between two dates) is supported; hedging a possible reading and leaving the choice to the author is "
    "supported. An action that only asks the author what the takeaway is, without proposing one, is correct. "
    "It is incorrect if it asserts as the takeaway something the passage does not show."
)


def _is_data_issue(expected: ResolvedIssue) -> bool:
    return expected.title == DATA_TITLE


JUDGE_CRITERIA = [
    JudgeCriterion(key="action_specific", criterion=SPECIFIC_CRITERION, scope="expected", passage="section"),
    JudgeCriterion(
        key="takeaway_within_evidence",
        criterion=WITHIN_EVIDENCE_CRITERION,
        scope="expected",
        passage="section",
        applies_to=_is_data_issue,
    ),
]

JUDGE_DESCRIPTIONS = {
    "action_specific": "Graded per detected issue: the suggested action says concretely what to do about this passage, not advice that fits any report (C=1, P=0.5, I=0).",
    "takeaway_within_evidence": "Graded per detected data dump: any takeaway the suggested action proposes is supported by the passage's own figures (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "no_rule_reference": "Share of reported issues that explain the problem without citing editing rules, guidelines or a style guide; NaN when nothing was reported.",
}

SCORE_LABELS = {
    "no_rule_reference": "No rule cited",
    "action_specific": "Specific action",
    "takeaway_within_evidence": "Within evidence",
}
