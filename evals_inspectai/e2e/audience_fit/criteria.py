"""What Audience Fit is judged on, beyond the generic layers.

The workflow proposes no edits, so its fixes live in the suggested action and
every criterion grades that. Besides the anchor and the suggested action, the
grader sees the source text the action has to agree with: the anchor's
paragraph for a paragraph of technical language, so a changed or dropped
finding shows; the whole report for a technical passage, which runs over
several paragraphs the anchor's paragraph does not show, and for the audience
issues, so an audience the report does not point to, or a conflicting audience
it never names, shows.
"""

from evals_inspectai.common.issue_inventory import ResolvedIssue
from evals_inspectai.common.issue_judge import JudgeCriterion

TECHNICAL_TITLE = "Technical Language"
PASSAGE_TITLE = "Technical Language: Move to Appendix"
AUDIENCE_TITLES = {"Target Audience Missing", "Target Audience Too Vague"}
CONFLICT_TITLE = "Target Audience Conflict"

PLAIN_ALTERNATIVE_CRITERION = (
    "The paragraph was flagged because the wording quoted as the sentence uses technical language (statistical "
    "or methodological terms, notation, or a field's terms of art) that the report's non-technical audience, "
    "such as policymakers or people who run public services, would not follow. The suggested action either "
    "gives a plain-language alternative for the technical wording, in everyday words that say what the result "
    "means for the reader, or says to move the technical detail to an appendix while keeping its plain upshot "
    "in the main text, or both. Any number from the paragraph it restates is unchanged. It is incorrect if it "
    "offers no alternative and no appendix move, if its alternative is itself technical, if it changes a number "
    "the paragraph reports as a finding or drops one from the upshot it says to keep, or if its alternative "
    "claims more than the paragraph does (for example, turning an association into a cause)."
)

PASSAGE_CRITERION = (
    "The sentence opens a passage of technical detail (a model specification, an estimation procedure, "
    "equations, robustness checks), two or more consecutive main-body paragraphs or a subsection, that the "
    "report's non-technical audience, such as policymakers or people who run public services, does not need "
    "in the main text. Find the passage in the report. The suggested action says to move the passage to an "
    "appendix and names the plain point the main body should keep in its place, in everyday words, drawn "
    "from what the passage itself concludes. Any number from the passage it restates is unchanged. It is "
    "incorrect if it does not say to move the passage, if it names no plain point to keep, if that point is "
    "itself technical, if it changes a number the passage reports or contradicts what the passage concludes, "
    "or if it claims more than the passage does (for example, turning an association into a cause)."
)

AUDIENCE_CRITERION = (
    "The sentence is where a report's target audience is missing or named only by a generic label such as "
    "'policymakers' or 'stakeholders'. The suggested action proposes a specific audience, one narrowed by a "
    "level of government, a kind of organization, a role or a field of practice (for example 'state workforce "
    "development offices' or 'county public health directors'), and presents it as a suggestion for the author "
    "to confirm rather than as a fact about who the author meant. The audience fits the report: it is among those "
    "who could act on the findings as the report presents them, such as whoever its recommendations address or "
    "who delivers the service it studies. It is incorrect if it only says to name an audience without proposing "
    "one, if the audience it proposes is itself a generic label, if the report gives no reason to think that "
    "audience could act on its findings, or if it asks for an elaborate description of several audiences when "
    "one would do."
)

CONFLICT_CRITERION = (
    "The sentence is the introduction's description of a report's target audience, which conflicts with a "
    "substantively different audience named in the report's front matter. The suggested action names or quotes "
    "both audiences as the report describes them, the one in this sentence and the one in the front matter, and "
    "asks the author to settle on one of them (or to reconcile them into one description). It may recommend which "
    "to keep, as long as the choice is left to the author. It is incorrect if it names only one of the audiences, "
    "if either audience it names is not the one the report states, if it does not ask the author to settle the "
    "conflict, or if it states as fact which audience the author meant."
)


def _technical(expected: ResolvedIssue) -> bool:
    title = expected.title
    return (
        title is not None
        and title.startswith(TECHNICAL_TITLE)
        and title != PASSAGE_TITLE
    )


def _passage(expected: ResolvedIssue) -> bool:
    return expected.title == PASSAGE_TITLE


def _audience(expected: ResolvedIssue) -> bool:
    return expected.title in AUDIENCE_TITLES


def _conflict(expected: ResolvedIssue) -> bool:
    return expected.title == CONFLICT_TITLE


JUDGE_DESCRIPTIONS = {
    "action_plain_alternative": "Graded per technical-language paragraph: the suggested action gives a plain-language alternative or an appendix move, keeping every number in the paragraph and claiming no more than it (C=1, P=0.5, I=0).",
    "action_passage_upshot": "Graded per technical passage, with the whole report in view: the suggested action says to move the passage to an appendix and names the plain point to keep, true to every number and to what the passage concludes (C=1, P=0.5, I=0).",
    "action_specific_audience": "Graded per missing or vague audience issue: the suggested action proposes one specific audience that fits the report, as a suggestion for the author to confirm (C=1, P=0.5, I=0).",
    "action_settle_conflict": "Graded per audience conflict issue: the suggested action names both audiences as the report states them and asks the author to settle on one (C=1, P=0.5, I=0).",
}

JUDGE_CRITERIA = [
    JudgeCriterion(
        key="action_plain_alternative",
        criterion=PLAIN_ALTERNATIVE_CRITERION,
        scope="expected",
        applies_to=_technical,
        passage="section",
    ),
    JudgeCriterion(
        key="action_passage_upshot",
        criterion=PASSAGE_CRITERION,
        scope="expected",
        applies_to=_passage,
        passage="document",
    ),
    JudgeCriterion(
        key="action_specific_audience",
        criterion=AUDIENCE_CRITERION,
        scope="expected",
        applies_to=_audience,
        passage="document",
    ),
    JudgeCriterion(
        key="action_settle_conflict",
        criterion=CONFLICT_CRITERION,
        scope="expected",
        applies_to=_conflict,
        passage="document",
    ),
]

SCORE_LABELS = {
    "action_plain_alternative": "Plain alternative",
    "action_passage_upshot": "Passage upshot",
    "action_specific_audience": "Specific audience",
    "action_settle_conflict": "Settle conflict",
}
