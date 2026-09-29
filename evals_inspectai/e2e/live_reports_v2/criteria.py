"""What Live Reports is judged on, beyond the generic layers.

Detection says a run flagged the claim later evidence changed; it cannot say
the evidence it found is what changed it, and the sources come from live web
search, so no dataset can list them. One graded criterion therefore compares
the newer evidence, as the issue describes it, with the labeller's account of
what overturned or updated the claim (the expected issue's ``rationale``).
Another grades whether the suggested action says how to revise the claim. The
deterministic source checks (``source_citations``) require a findable citation
published no earlier than the document, and not one the document already cites.
"""

from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.source_citations import SOURCE_DESCRIPTIONS, window_description

EVIDENCE_CRITERION = (
    "The reviewer reported that newer evidence, published after the document, updates or challenges a claim in "
    "it, and the labeller has described what actually changed. The reviewer's sources come from a web search, so "
    "they need not be the ones the labeller names. Grade whether the newer evidence, as the reviewer describes "
    "it, is the kind of development that changed this claim, and whether the reviewer makes clear that the claim "
    "no longer holds as stated. It is correct if it names that development, or evidence to the same effect, and "
    "says the claim is contradicted, outdated or in need of revision, in any words (reframing a forecast as a "
    "past expectation that proved wrong is such a revision). It is partially correct if it is on the topic but "
    "misses the main development, or offers contradicting evidence only as added context while leaving the claim "
    "standing. It is incorrect if it presents the claim as still holding, cites evidence that does not bear on "
    "it, or does not say what the newer evidence shows."
)

ACTION_CRITERION = (
    "The reviewer reported that newer evidence updates or challenges a claim in a document, and the passage the "
    "claim sits in is shown. Grade whether the suggested action tells the author concretely how to revise this "
    "claim: what it should now say, or which qualification or citation to add and where. Generic advice "
    "(\"update the section\", \"review recent literature\") is incorrect. An action that would keep an overturned "
    "claim and only add a citation is partially correct."
)

JUDGE_CRITERIA = [
    JudgeCriterion(key="evidence_updates_claim", criterion=EVIDENCE_CRITERION, scope="expected", passage="section", reads="analysis", reference=True),
    JudgeCriterion(key="action_revises_claim", criterion=ACTION_CRITERION, scope="expected", passage="section"),
]

JUDGE_DESCRIPTIONS = {
    "evidence_updates_claim": "Graded per covered claim against the labeller's account of what changed: the newer evidence is that development and its bearing is stated correctly (C=1, P=0.5, I=0).",
    "action_revises_claim": "Graded per covered claim against its passage: the suggested action says concretely how to revise the claim (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "cites_source": SOURCE_DESCRIPTIONS["cites_source"],
    "sources_in_window": window_description(after=True),
    "report_lists_sources": SOURCE_DESCRIPTIONS["report_lists_sources"],
    "not_already_cited": SOURCE_DESCRIPTIONS["not_already_cited"],
}

SCORE_LABELS = {
    "cites_source": "Full citation",
    "sources_in_window": "After pub date",
    "report_lists_sources": "Report lists",
    "not_already_cited": "Not already cited",
    "evidence_updates_claim": "Evidence fits",
    "action_revises_claim": "Action revises",
}
