"""The judged-criteria loop with a scripted grader: what it sends and what it scores."""

import math
from typing import cast

import pytest
from inspect_ai.model import Model

from evals_inspectai.common.issue_judge import JudgeCriterion, judge_sample
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.simple_deep_agent_types import IssueItem, ProposedEdit

DOC = "# Title\n\nNine countries signed the treaty in 1962.\n\nThe institute was established in 1962. It grew fast.\n"


class _Completion:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _Grader:
    """Answers every prompt with the same grade and keeps the prompts it saw."""

    def __init__(self, grade: str = "GRADE: C") -> None:
        self.grade = grade
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> _Completion:
        self.prompts.append(prompt)
        return _Completion(self.grade)


def _expected(**kw) -> ResolvedIssue:
    base = {"id": "established", "title": "Passive Voice", "anchor": "The institute was established", "line": 5}
    return ResolvedIssue(**{**base, **kw})


def _inventory(expected: ResolvedIssue) -> ResolvedInventory:
    return ResolvedInventory(document=DOC, expected_issues=[expected], decoys=[])


MEANING = JudgeCriterion(key="meaning", criterion="Meaning is preserved.", scope="edit")
ASKED = JudgeCriterion(
    key="asked", criterion="The action asks for the actor.", scope="expected", applies_to=lambda e: e.edit_expected is False
)


@pytest.mark.asyncio
async def test_edit_prompt_carries_the_sentence_paragraph():
    grader = _Grader()
    edit = ProposedEdit(original_text="The institute was established in 1962.", replacement_text="Nine countries established the institute in 1962.", start_line=5, end_line=5)
    issue = IssueItem(title="Passive Voice", start_line=5, end_line=5, edits=[edit])

    values, _ = await judge_sample(cast(Model, grader), [issue], _inventory(_expected(edit_expected=True)), [MEANING])

    assert values == {"meaning": 1.0}
    assert len(grader.prompts) == 1
    assert "[Paragraph the sentence sits in]: The institute was established in 1962. It grew fast." in grader.prompts[0]


@pytest.mark.asyncio
async def test_detected_issue_without_a_suggested_action_fails_the_action_criterion():
    grader = _Grader()
    issue = IssueItem(title="Passive Voice", start_line=5, end_line=5, suggested_action=None)

    values, explanation = await judge_sample(cast(Model, grader), [issue], _inventory(_expected(edit_expected=False)), [ASKED])

    assert values == {"asked": 0.0}
    assert grader.prompts == []
    assert "no suggested action" in explanation


@pytest.mark.asyncio
async def test_action_criterion_grades_the_suggested_action():
    grader = _Grader("GRADE: I")
    issue = IssueItem(title="Passive Voice", start_line=5, end_line=5, suggested_action="Name who established the institute.")

    values, _ = await judge_sample(cast(Model, grader), [issue], _inventory(_expected(edit_expected=False)), [ASKED])

    assert values == {"asked": 0.0}
    assert "Name who established the institute." in grader.prompts[0]


@pytest.mark.asyncio
async def test_undetected_issue_leaves_every_criterion_unscored():
    grader = _Grader()

    values, explanation = await judge_sample(cast(Model, grader), [], _inventory(_expected(edit_expected=False)), [MEANING, ASKED])

    assert all(math.isnan(v) for v in values.values()) and grader.prompts == []
    assert explanation == "all judged criteria passed"
