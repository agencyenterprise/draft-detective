"""Per-item model grading for issue-inventory evals, on Inspect's grading protocol.

Inspect's ``model_graded_fact`` / ``model_graded_qa`` grade one answer per
sample. An inventory sample holds several proposed edits, each needing its
own verdict, so those scorers cannot be used as they are. This module keeps
their protocol and only adds the loop: each criterion is graded with Inspect's
own ``{question}`` / ``{answer}`` / ``{criterion}`` / ``{instructions}``
template shape, its ``default_instructions`` (C / P / I with partial credit)
and its ``DEFAULT_GRADE_PATTERN``, one grader call per edit or expected, never
one call weighing the whole run. C maps to 1.0, P to 0.5, I to 0.0, as in the
repo's other judged criteria. Repeated calls take the median.

A criterion with nothing to judge in a sample is NaN, which Inspect leaves out
of the mean. The criteria themselves live with the workflow they judge.
"""

import asyncio
import math
import re
import statistics
from typing import Callable, Literal, Optional, Sequence

from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.scorer._model import (  # type: ignore[attr-defined]
    DEFAULT_GRADE_PATTERN,
    default_instructions,
)
from inspect_ai.solver import TaskState
from pydantic import BaseModel, ConfigDict

from evals_inspectai.common.issue_checks import (
    PER_KEY_METRICS,
    edits_for,
    hit_pairs,
    inventory_from_state,
    issues_from_state,
)
from evals_inspectai.common.scorers import DEFAULT_GRADER_MODEL, GRADE_VALUES
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.common.issue_inventory import ResolvedIssue, ResolvedInventory

# The same shape as Inspect's model-graded templates, with the two texts an
# edit-level criterion compares laid out explicitly.
EDIT_TEMPLATE = """You are grading one proposed edit to a sentence in a research report against one criterion.

[BEGIN DATA]
************
[Paragraph the sentence sits in]: {paragraph}
************
[Original sentence]: {question}
************
[Proposed replacement]: {answer}
************
[Criterion]: {criterion}
************
[END DATA]

{instructions}
"""

ISSUE_TEMPLATE = """You are grading one reviewer issue against one criterion.

[BEGIN DATA]
************
[Sentence the issue is about]: {question}
************
[Reviewer's suggested action]: {answer}
************
[Criterion]: {criterion}
************
[END DATA]

{instructions}
"""

# For an issue about a header, the header alone is no evidence: the grader also
# sees the section it heads, so it can tell whether a suggested header says what
# the section shows.
PASSAGE_ISSUE_TEMPLATE = """You are grading one reviewer issue against one criterion.

[BEGIN DATA]
************
[Passage the issue is about]: {passage}
************
[Text the issue quotes or is anchored to]: {question}
************
[Reviewer's suggested action]: {answer}
************
[Criterion]: {criterion}
************
[END DATA]

{instructions}
"""

_HEADING_RE = re.compile(r"^(#{1,6})\s")
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


class JudgeCriterion(BaseModel):
    """One criterion the grader applies per edit or per expected."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str
    criterion: str
    scope: Literal["edit", "expected"] = "edit"
    # Which expected issues this criterion applies to; None means every detected one.
    applies_to: Optional[Callable[[ResolvedIssue], bool]] = None
    # What an expected-scope criterion shows the grader besides the anchor:
    # nothing, or the section the anchor's line opens (see ``section_text``).
    passage: Literal["none", "section"] = "none"


def parse_grade(completion: str) -> float:
    match = re.search(DEFAULT_GRADE_PATTERN, completion)
    return GRADE_VALUES.get(match.group(1), 0.0) if match else 0.0


async def grade(grader: Model, prompt: str, calls: int) -> tuple[float, str]:
    """The median grade over ``calls`` grader calls, plus the first reasoning."""
    results = await asyncio.gather(*(grader.generate(prompt) for _ in range(calls)))
    return statistics.median(parse_grade(r.completion) for r in results), results[0].completion.strip()


def edit_prompt(criterion: str, paragraph: str, original: str, replacement: str) -> str:
    return EDIT_TEMPLATE.format(
        paragraph=paragraph,
        question=original,
        answer=replacement,
        criterion=criterion,
        instructions=default_instructions(partial_credit=True),
    )


def issue_prompt(criterion: str, sentence: str, suggested_action: str) -> str:
    return ISSUE_TEMPLATE.format(
        question=sentence,
        answer=suggested_action,
        criterion=criterion,
        instructions=default_instructions(partial_credit=True),
    )


def passage_issue_prompt(criterion: str, passage: str, anchor: str, suggested_action: str) -> str:
    return PASSAGE_ISSUE_TEMPLATE.format(
        passage=passage,
        question=anchor,
        answer=suggested_action,
        criterion=criterion,
        instructions=default_instructions(partial_credit=True),
    )


def _heading_levels(lines: list[str]) -> list[int]:
    """The markdown heading level of each line, 0 for a line that is not a heading,
    including a ``#`` line inside a fenced code block."""
    levels: list[int] = []
    fenced = False
    for line in lines:
        if _FENCE_RE.match(line):
            fenced = not fenced
        heading = None if fenced else _HEADING_RE.match(line)
        levels.append(len(heading.group(1)) if heading else 0)
    return levels


def _paragraph_text(lines: list[str], line: int) -> str:
    """The paragraph holding ``line``: the lines around it up to a blank line, a
    heading or the next list item, so a paragraph wrapped across several lines is
    passed whole and a list item is passed without its siblings."""
    if not 0 < line <= len(lines):
        return ""
    levels = _heading_levels(lines)
    if levels[line - 1]:
        return lines[line - 1]

    def inside(i: int) -> bool:
        return 0 <= i < len(lines) and lines[i].strip() != "" and levels[i] == 0

    start = end = line - 1
    while inside(start - 1) and not _LIST_ITEM_RE.match(lines[start]):
        start -= 1
    while inside(end + 1) and not _LIST_ITEM_RE.match(lines[end + 1]):
        end += 1
    return "\n".join(lines[start : end + 1]).strip()


def section_text(document: str, line: int) -> str:
    """The section a markdown heading on ``line`` opens: the heading and every line
    up to the next heading of the same or a higher level. A line that is not a
    heading gives the paragraph it sits in."""
    lines = document.split("\n")
    if not 0 < line <= len(lines):
        return ""
    levels = _heading_levels(lines)
    level = levels[line - 1]
    if not level:
        return _paragraph_text(lines, line)
    end = line
    while end < len(lines) and not 0 < levels[end] <= level:
        end += 1
    return "\n".join(lines[line - 1 : end]).strip()


def _paragraph(expected: ResolvedIssue, document: str) -> str:
    return _paragraph_text(document.split("\n"), expected.line)


async def judge_sample(
    grader: Model,
    issues: Sequence[IssueItem],
    inventory: ResolvedInventory,
    criteria: Sequence[JudgeCriterion],
    calls: int = 1,
    one_to_one: bool = False,
) -> tuple[dict[str, float], str]:
    """All criteria for one sample, NaN where a criterion has nothing to judge.

    Expected issues are paired with reports by ``hit_pairs``, the same pairing
    the deterministic layers use (canonical order, and one-to-one when the
    workflow asks for it), so the judge grades the report those layers scored.

    An expected-scope criterion judges the issue's suggested action; a detected
    issue that offers none has failed it (the check is what the action says), so
    that scores 0 rather than NaN.
    """
    values: dict[str, list[float]] = {c.key: [] for c in criteria}
    notes: list[str] = []

    def record(criterion: JudgeCriterion, expected: ResolvedIssue, value: float, why: str) -> None:
        values[criterion.key].append(value)
        if value < 1.0:
            notes.append(f"{expected.id} {criterion.key} {value}: {why.splitlines()[0][:160]}")

    for expected, issue in hit_pairs(issues, inventory, one_to_one)[1]:
        paragraph = _paragraph(expected, inventory.document)
        for criterion in criteria:
            if criterion.applies_to is not None and not criterion.applies_to(expected):
                continue
            if criterion.scope == "edit":
                for edit in edits_for(expected, issue):
                    prompt = edit_prompt(criterion.criterion, paragraph, edit.original_text, edit.replacement_text)
                    record(criterion, expected, *await grade(grader, prompt, calls))
            elif not issue.suggested_action:
                record(criterion, expected, 0.0, "no suggested action to judge")
            elif criterion.passage == "section":
                passage = section_text(inventory.document, expected.line)
                prompt = passage_issue_prompt(criterion.criterion, passage, expected.anchor, issue.suggested_action)
                record(criterion, expected, *await grade(grader, prompt, calls))
            else:
                prompt = issue_prompt(criterion.criterion, expected.anchor, issue.suggested_action)
                record(criterion, expected, *await grade(grader, prompt, calls))

    return (
        {key: (sum(v) / len(v) if v else math.nan) for key, v in values.items()},
        " | ".join(notes) if notes else "all judged criteria passed",
    )


@scorer(metrics=PER_KEY_METRICS)
def judged_criteria(criteria: Sequence[JudgeCriterion], calls: int = 1, one_to_one: bool = False) -> Scorer:
    """A workflow's judged criteria, one focused grader call per item.

    The grader is Inspect's ``grader`` model role (``--model-role grader=...``),
    falling back to the repo's default grader model. ``calls`` grader calls are
    made per item and the median grade kept. ``one_to_one`` must match what the
    workflow's ``issue_checks`` uses, so both layers pair the same reports.
    """

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state)
        if error:
            return Score(value={c.key: 0.0 for c in criteria}, explanation=error)
        grader = get_model(role="grader", default=DEFAULT_GRADER_MODEL)
        values, explanation = await judge_sample(
            grader, issues, inventory_from_state(state), criteria, calls=calls, one_to_one=one_to_one
        )
        return Score(value=values, explanation=explanation)

    return score
