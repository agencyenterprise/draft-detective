"""What Literature Review is judged on, beyond the generic layers.

Detection says a run recommended something for the right claim; it cannot say
the recommendation is any good, and the sources come from live web search, so
no dataset can list them. One graded criterion therefore compares the reported
source, as the issue describes it, with the labeller's account of the
literature the claim needs (the expected issue's ``rationale``): does it bear on
this claim, and is its direction (supporting, conflicting) stated as the
literature has it. Another grades whether the suggested action says what to
do with the source at this claim. Neither can tell a real source from a
fabricated one; the deterministic source checks (``source_citations``) at least
require a findable citation in the right date window.
"""

from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.source_citations import SOURCE_DESCRIPTIONS, window_description

SOURCE_CRITERION = (
    "The reviewer recommended a source for a claim in a document, and the labeller has described the "
    "literature this claim should engage with. The reviewer's sources come from a web search, so they need not be "
    "the ones the labeller names. Grade whether the recommended source, as the reviewer describes it, bears "
    "directly on this specific claim, and whether the reviewer says correctly whether it supports or conflicts "
    "with the claim given what the labeller says the literature shows. It is correct if the source's findings bear "
    "on whether the claim holds and its stated direction fits; a source need not test the document's exact case "
    "(a study of label wording bears on a claim about one label), and a review or a corrected report of a study "
    "counts as well as the study. It is partially correct if the source is on the broader topic but its findings "
    "do not bear on whether this claim holds, or its direction is left unstated. It is incorrect if the source is off "
    "topic, if it is presented as supporting a claim the literature contradicts (or the reverse), or if the "
    "analysis does not say what the source found."
)

ACTION_CRITERION = (
    "The reviewer recommended a source for a claim in a document, and the passage the claim sits in is shown. "
    "Grade whether the suggested action tells the author concretely what to do at this claim: add the citation "
    "at this sentence, cite an existing reference here, or revise or qualify the claim in a stated way because of "
    "what the source shows. Generic advice (\"consider the literature\", \"add more references\") is incorrect. "
    "An action asking the author to cite a supporting source for a claim the passage makes more strongly than "
    "that source supports, without qualifying the claim, is partially correct."
)

JUDGE_CRITERIA = [
    JudgeCriterion(key="source_bears_on_claim", criterion=SOURCE_CRITERION, scope="expected", passage="section", reads="analysis", reference=True),
    JudgeCriterion(key="action_fits", criterion=ACTION_CRITERION, scope="expected", passage="section"),
]

JUDGE_DESCRIPTIONS = {
    "source_bears_on_claim": "Graded per covered claim against the labeller's account of its literature: the recommended source bears on this claim and its stated direction fits (C=1, P=0.5, I=0).",
    "action_fits": "Graded per covered claim against its passage: the suggested action says concretely what to do with the source at this claim (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "cites_source": SOURCE_DESCRIPTIONS["cites_source"],
    "sources_in_window": window_description(after=False),
    "report_lists_sources": SOURCE_DESCRIPTIONS["report_lists_sources"],
}

SCORE_LABELS = {
    "cites_source": "Full citation",
    "sources_in_window": "Before pub date",
    "report_lists_sources": "Report lists",
    "source_bears_on_claim": "Source fits claim",
    "action_fits": "Action fits",
}
