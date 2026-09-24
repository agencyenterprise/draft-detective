"""The judged-criteria loop with a scripted grader: what it sends and what it scores."""

import math
from typing import cast

import pytest
from inspect_ai.model import Model

from evals_inspectai.common.issue_judge import JudgeCriterion, judge_sample, section_text
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


@pytest.mark.asyncio
@pytest.mark.parametrize("reversed_order", [False, True])
async def test_judge_grades_the_same_report_as_the_deterministic_pairing_in_either_order(reversed_order):
    from evals_inspectai.common.issue_checks import hit_pairs

    expected = _expected(title=None, edit_expected=True)
    original = "The institute was established in 1962."
    first = IssueItem(title="Passive Voice", description="Rewrite A.", severity="low", start_line=5, end_line=5,
                      edits=[ProposedEdit(original_text=original, replacement_text="Nine countries established the institute in 1962.", start_line=5, end_line=5)])
    second = IssueItem(title="Passive Voice", description="Rewrite B.", severity="low", start_line=5, end_line=5,
                       edits=[ProposedEdit(original_text=original, replacement_text="The institute began in 1962.", start_line=5, end_line=5)])
    issues = [second, first] if reversed_order else [first, second]
    grader = _Grader()

    await judge_sample(cast(Model, grader), issues, _inventory(expected), [MEANING])

    (_, paired), = hit_pairs(issues, _inventory(expected))[1]
    assert len(grader.prompts) == 1
    assert paired.edits[0].replacement_text in grader.prompts[0], "the judge graded the report the deterministic layer paired"
    assert "Rewrite A." < "Rewrite B." and paired.description == "Rewrite A.", "canonical order, not report order"


SECTION_DOC = "# Title\n\n## Findings\n\nScores rose 5 points.\n\n### Detail\n\nMostly in grade 3.\n\n## Methods\n\nWe used records.\n"


def test_section_text_runs_to_the_next_heading_of_the_same_level():
    assert section_text(SECTION_DOC, 3) == "## Findings\n\nScores rose 5 points.\n\n### Detail\n\nMostly in grade 3."
    assert section_text(SECTION_DOC, 7) == "### Detail\n\nMostly in grade 3."
    assert section_text(SECTION_DOC, 13) == "We used records."
    assert section_text(SECTION_DOC, 99) == ""


def test_section_text_gives_a_wrapped_paragraph_whole():
    document = "## Findings\n\nScores rose 5 points in grade 3\nand 2 points in grade 4,\nwhile grade 5 held.\n\nNext paragraph.\n"
    wrapped = "Scores rose 5 points in grade 3\nand 2 points in grade 4,\nwhile grade 5 held."
    assert section_text(document, 3) == wrapped
    assert section_text(document, 4) == wrapped
    assert section_text(document, 5) == wrapped
    assert section_text("Intro.\n## Findings\nScores rose.\n", 3) == "Scores rose.", "stops at a heading"


@pytest.mark.asyncio
async def test_section_passage_criterion_shows_the_grader_the_section():
    grader = _Grader()
    criterion = JudgeCriterion(key="supported", criterion="Supported.", scope="expected", passage="section")
    expected = ResolvedIssue(id="findings", title="Vague Header", anchor="## Findings", line=3)
    issue = IssueItem(title="Vague Header", start_line=3, end_line=3, suggested_action='Suggested header: "Scores Rose"')
    inventory = ResolvedInventory(document=SECTION_DOC, expected_issues=[expected], decoys=[])

    values, _ = await judge_sample(cast(Model, grader), [issue], inventory, [criterion])

    assert values == {"supported": 1.0}
    assert "[Passage the issue is about]: ## Findings\n\nScores rose 5 points." in grader.prompts[0]
    assert "## Methods" not in grader.prompts[0]


@pytest.mark.asyncio
async def test_default_expected_criterion_prompt_is_unchanged():
    grader = _Grader()
    issue = IssueItem(title="Passive Voice", start_line=5, end_line=5, suggested_action="Name who established the institute.")

    await judge_sample(cast(Model, grader), [issue], _inventory(_expected(edit_expected=False)), [ASKED])

    assert grader.prompts[0].startswith("You are grading one reviewer issue against one criterion.\n\n[BEGIN DATA]\n************\n[Sentence the issue is about]:")
    assert "[Passage the issue is about]" not in grader.prompts[0]
