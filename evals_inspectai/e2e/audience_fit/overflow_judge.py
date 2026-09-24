"""The judged half of Audience Fit's overflow check: the summary's plain alternatives.

``overflow_checks`` confirms the ``Technical Language: Further Paragraphs``
summary spans every remaining technical paragraph and quotes its term, but not
that it gives each one a plain alternative. The generic judged criteria cannot
see that either: pairing is one-to-one, so the single summary is graded against
only one of the paragraphs it covers. This scorer grades the summary once per
remaining paragraph, on ``issue_judge``'s protocol, and keeps the mean. Every
other sample is NaN.
"""

import asyncio
import math
from typing import Sequence

from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.scorer._model import default_instructions  # type: ignore[attr-defined]
from inspect_ai.solver import TaskState

from evals_inspectai.common.issue_checks import (
    PER_KEY_METRICS,
    inventory_from_state,
    issues_from_state,
)
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.issue_judge import grade
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.audience_fit.overflow import (
    SUMMARY_TITLE,
    overflow_split,
    overflow_summaries,
)

SUMMARY_KEY = "overflow_summary_alternatives"
SUMMARY_DESCRIPTIONS = {
    SUMMARY_KEY: f"On the overflow sample, graded per remaining technical paragraph: the '{SUMMARY_TITLE}' summary gives that paragraph's term a plain-language alternative or an appendix move (C=1, P=0.5, I=0; 0 when there is no single summary).",
}
SUMMARY_LABELS = {SUMMARY_KEY: "Summary alternatives"}

SUMMARY_TEMPLATE = """You are grading one reviewer issue that summarizes several paragraphs of a research report, for one of those paragraphs, against one criterion.

[BEGIN DATA]
************
[Paragraph]: {question}
************
[Technical term in the paragraph]: {term}
************
[Reviewer's summary issue]: {answer}
************
[Criterion]: {criterion}
************
[END DATA]

{instructions}
"""

SUMMARY_CRITERION = (
    "The reviewer found more paragraphs of technical language than it reports one by one, and summarized the rest "
    "in this one issue for a non-technical audience, such as policymakers or people who run public services. For "
    "the paragraph and term above, the summary either gives a plain-language alternative for the term, in everyday "
    "words that say what it means for the reader, or says to move the technical detail to an appendix while keeping "
    "its plain upshot in the main text. Any number it restates is unchanged. It is incorrect if the summary does "
    "not mention this paragraph or term, if it names the term without an alternative or an appendix move, if its "
    "alternative is itself technical, or if it changes a number the paragraph reports."
)


def summary_text(issue: IssueItem) -> str:
    """Everything the summary says, as the grader reads it."""
    parts = [issue.description, issue.long_description, issue.suggested_action]
    return "\n\n".join(p for p in parts if p)


def summary_prompt(paragraph: str, expected: ResolvedIssue, summary: IssueItem) -> str:
    return SUMMARY_TEMPLATE.format(
        question=paragraph,
        term=expected.anchor,
        answer=summary_text(summary),
        criterion=SUMMARY_CRITERION,
        instructions=default_instructions(partial_credit=True),
    )


def _line(document: str, number: int) -> str:
    lines = document.split("\n")
    return lines[number - 1] if 0 < number <= len(lines) else ""


async def summary_alternative_scores(
    grader: Model,
    issues: Sequence[IssueItem],
    inventory: ResolvedInventory,
    calls: int = 1,
) -> tuple[dict[str, float], str]:
    """The mean grade over the remaining paragraphs; NaN unless this is the overflow sample."""
    split = overflow_split(inventory)
    if split is None:
        return {SUMMARY_KEY: math.nan}, "not an overflow sample"
    summaries = overflow_summaries(issues)
    if len(summaries) != 1:
        note = f"{len(summaries)} summaries; expected exactly one to judge"
        return {SUMMARY_KEY: 0.0}, note
    rest = split[1]
    prompts = [
        summary_prompt(_line(inventory.document, e.line), e, summaries[0]) for e in rest
    ]
    results = await asyncio.gather(*(grade(grader, p, calls) for p in prompts))
    notes = [
        f"{e.id} {value}: {why.splitlines()[0][:160]}"
        for e, (value, why) in zip(rest, results)
        if value < 1.0
    ]
    mean = sum(value for value, _ in results) / len(results)
    return {SUMMARY_KEY: mean}, (
        " | ".join(notes) if notes else "every remaining paragraph has its alternative"
    )


@scorer(metrics=PER_KEY_METRICS)
def overflow_judge(calls: int = 1) -> Scorer:
    """Grades the overflow summary once per remaining paragraph, with the ``grader`` model role."""

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state)
        if error:
            return Score(value={SUMMARY_KEY: 0.0}, explanation=error)
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        values, explanation = await summary_alternative_scores(
            grader, issues, inventory_from_state(state), calls
        )
        return Score(value=values, explanation=explanation)

    return score
