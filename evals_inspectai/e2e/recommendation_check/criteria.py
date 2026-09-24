"""What Recommendation Check is judged on, beyond the generic layers.

The workflow proposes no edits, so there is nothing to grade per edit. What
the generic scorers cannot see is whether the fix in an actionability,
audience or length issue is usable: a concrete action rather than another
vague one, a question about who should act rather than a guessed actor, and
named recommendations to keep or cut. Each is graded on the issue's
suggested action, against the recommendation it is anchored to, one grader
call per detected issue of that kind (``issue_judge``'s protocol and default
grader model).
"""

from typing import Callable

from evals_inspectai.common.issue_inventory import ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion

NOT_ACTIONABLE_TITLE = "Recommendation Not Actionable"
AUDIENCE_TITLE = "Recommendation Audience Unclear"
TOO_MANY_TITLE = "Too Many Recommendations"

ACTION_CRITERION = (
    "The recommendation was flagged because it does not say what to do. The suggested action either proposes a "
    "concrete step a reader could take and later check had been taken (fund, require, publish, assign, measure a "
    "named thing), or asks the author what action they mean. It is incorrect if the proposed action is as vague as "
    "the original (strengthen, enhance, improve, address, prioritize an abstract object), or if it only says the "
    "recommendation should be more actionable without saying how."
)

AUDIENCE_CRITERION = (
    "The recommendation was flagged because it does not make clear who should act on it. The suggested action asks "
    "the author to name who should act, and may offer candidate parties as options. It is incorrect if it only "
    "restates that the audience is unclear without asking for a specific party, or if it rewrites the recommendation "
    "around one actor as settled fact without leaving the choice to the author."
)

TOO_MANY_CRITERION = (
    "The document was flagged for making more than three recommendations. The suggested action names which "
    "recommendations to keep and which to merge, cut or move, by their content or number. It is incorrect if it "
    "only says to reduce the number of recommendations without saying which."
)


def _titled(title: str) -> Callable[[ResolvedIssue], bool]:
    def applies(expected: ResolvedIssue) -> bool:
        return expected.title == title

    return applies


SCORE_LABELS = {
    "action_concrete": "Action concrete",
    "audience_asked": "Audience asked",
    "pare_down_named": "Pare-down named",
}

JUDGE_DESCRIPTIONS = {
    "action_concrete": "Graded per not-actionable issue: the suggested action proposes a concrete, checkable step or asks the author what action they mean (C=1, P=0.5, I=0).",
    "audience_asked": "Graded per unclear-audience issue: the suggested action asks the author to name who should act, candidates allowed, without settling on a guess (C=1, P=0.5, I=0).",
    "pare_down_named": "Graded per too-many issue: the suggested action names which recommendations to keep and which to merge, cut or move (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(key="action_concrete", criterion=ACTION_CRITERION, scope="expected", applies_to=_titled(NOT_ACTIONABLE_TITLE)),
    JudgeCriterion(key="audience_asked", criterion=AUDIENCE_CRITERION, scope="expected", applies_to=_titled(AUDIENCE_TITLE)),
    JudgeCriterion(key="pare_down_named", criterion=TOO_MANY_CRITERION, scope="expected", applies_to=_titled(TOO_MANY_TITLE)),
]
