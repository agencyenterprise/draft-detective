"""What Audience Fit is judged on, beyond the generic layers.

The workflow proposes no edits, so its fixes live in the suggested action and
both criteria grade that. The grader sees only the anchor sentence and the
suggested action, never the document, so each criterion asks only what those
two texts can show.
"""

from evals_inspectai.common.issue_inventory import ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion

TECHNICAL_TITLE = "Technical Language"
AUDIENCE_TITLES = {"Target Audience Missing", "Target Audience Too Vague"}

PLAIN_ALTERNATIVE_CRITERION = (
    "The sentence was flagged because it uses technical language (statistical or methodological terms, "
    "notation, or a field's terms of art) that the report's non-technical audience, such as policymakers "
    "or people who run public services, would not follow. The suggested action either gives a plain-language "
    "alternative for the technical wording, in everyday words that say what the result means for the reader, "
    "or says to move the technical detail to an appendix while keeping its plain upshot in the main text, or "
    "both. Any number it restates is unchanged. It is incorrect if it offers no alternative and no appendix "
    "move, if its alternative is itself technical, if it changes or drops a number the sentence reports as a "
    "finding, or if its alternative claims more than the sentence does (for example, turning an association "
    "into a cause)."
)

AUDIENCE_CRITERION = (
    "The sentence is where a report's target audience is missing or named only by a generic label such as "
    "'policymakers' or 'stakeholders'. The suggested action proposes a specific audience, one narrowed by a "
    "level of government, a kind of organization, a role or a field of practice (for example 'state workforce "
    "development offices' or 'county public health directors'), and presents it as a suggestion for the author "
    "to confirm rather than as a fact about who the author meant. It is incorrect if it only says to name an "
    "audience without proposing one, if the audience it proposes is itself a generic label, or if it asks for "
    "an elaborate description of several audiences when one would do."
)


def _technical(expected: ResolvedIssue) -> bool:
    return expected.title is not None and expected.title.startswith(TECHNICAL_TITLE)


def _audience(expected: ResolvedIssue) -> bool:
    return expected.title in AUDIENCE_TITLES


JUDGE_DESCRIPTIONS = {
    "action_plain_alternative": "Graded per technical-language issue: the suggested action gives a plain-language alternative or an appendix move, keeping every number and claiming no more than the text (C=1, P=0.5, I=0).",
    "action_specific_audience": "Graded per missing or vague audience issue: the suggested action proposes one specific audience, as a suggestion for the author to confirm (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(
        key="action_plain_alternative",
        criterion=PLAIN_ALTERNATIVE_CRITERION,
        scope="expected",
        applies_to=_technical,
    ),
    JudgeCriterion(
        key="action_specific_audience",
        criterion=AUDIENCE_CRITERION,
        scope="expected",
        applies_to=_audience,
    ),
]

SCORE_LABELS = {"action_plain_alternative": "Plain alternative", "action_specific_audience": "Specific audience"}
