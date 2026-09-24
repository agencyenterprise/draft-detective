"""The Audience Fit eval: its dataset, task, which issues each judged criterion applies to, and the overflow check."""

import math
from pathlib import Path
from typing import cast

import pytest
from inspect_ai.model import Model

from evals_inspectai.common.issue_inventory import (
    ResolvedIssue,
    decoy_reasons,
    expects_edits,
    expects_titles,
    load_inventory_records,
)
from evals_inspectai.e2e.audience_fit.audience_fit_e2e import audience_fit_e2e
from evals_inspectai.e2e.audience_fit.criteria import JUDGE_CRITERIA
from evals_inspectai.e2e.audience_fit.overflow import (
    CAP,
    OVERFLOW_KEYS,
    overflow_scores,
    technical_paragraphs,
)
from evals_inspectai.e2e.audience_fit.overflow_judge import (
    SUMMARY_KEY,
    summary_alternative_scores,
)
from evals_inspectai.common.simple_deep_agent_types import IssueItem

DATASET = Path("evals_inspectai/e2e/audience_fit/dataset.yaml")


def _expected(title: str) -> ResolvedIssue:
    return ResolvedIssue(title=title, anchor="a", line=1, id="x")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 16
    expected = [e for r in records for e in r.expected_issues]
    assert {e.title for e in expected} == {
        "Target Audience Missing",
        "Target Audience Too Vague",
        "Target Audience Conflict",
        "Technical Language",
        "Technical Language: Move to Appendix",
    }
    assert sum(1 for r in records if not r.expected_issues) == 6, "six clean documents"
    assert {
        "specific_audience",
        "reworded_audience",
        "technical_audience",
        "audience_vocabulary",
        "explained_term",
        "appendix",
        "appendix_pointer",
        "quoted",
    } <= set(decoy_reasons(records))
    # The workflow proposes no edits, so the inventory expects none and names every title.
    assert expects_edits(records) is False
    assert expects_titles(records) is True
    assert all(e.edit_expected is None and e.edit is None for e in expected)
    # Exactly one record has more technical paragraphs than the cap; those past it are optional,
    # since one summary issue reports them all.
    overflow = [r for r in records if len(technical_paragraphs(r)) > CAP]
    assert len(overflow) == 1
    paragraphs = technical_paragraphs(overflow[0])
    assert all(e.required for e in paragraphs[:CAP]) and not any(
        e.required for e in paragraphs[CAP:]
    )


def test_each_criterion_applies_to_its_own_issues():
    by_key = {c.key: c for c in JUDGE_CRITERIA}
    plain, audience, conflict = (
        by_key["action_plain_alternative"],
        by_key["action_specific_audience"],
        by_key["action_settle_conflict"],
    )
    assert plain.applies_to is not None and audience.applies_to is not None
    assert conflict.applies_to is not None
    assert plain.applies_to(_expected("Technical Language"))
    assert plain.applies_to(_expected("Technical Language: Move to Appendix"))
    assert not plain.applies_to(_expected("Target Audience Missing"))
    assert audience.applies_to(_expected("Target Audience Missing"))
    assert audience.applies_to(_expected("Target Audience Too Vague"))
    # A conflict is settled by the author, not by a proposed audience.
    assert not audience.applies_to(_expected("Target Audience Conflict"))
    assert not audience.applies_to(_expected("Technical Language"))
    assert conflict.applies_to(_expected("Target Audience Conflict"))
    assert not conflict.applies_to(_expected("Target Audience Too Vague"))
    assert not conflict.applies_to(_expected("Technical Language"))
    # Each grader sees the source its action must agree with.
    assert plain.passage == "section"
    assert audience.passage == "document" and conflict.passage == "document"


def test_task_composes_the_inventory_scorers_and_its_judged_criteria():
    t = audience_fit_e2e()
    assert len(t.dataset) == 16 and len(t.scorer) == 5
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert "score__judged_criteria__action_plain_alternative" in columns
    assert "score__judged_criteria__action_settle_conflict" in columns
    assert "score__overflow_judge__overflow_summary_alternatives" in columns
    assert "score__decoy_checks__no_fp_technical_audience" in columns
    assert "score__overflow_checks__overflow_cap" in columns
    # No edits are expected, so no edit-hygiene column is emitted.
    assert not any("edit_" in c for c in columns)


def _overflow_inventory():
    records = load_inventory_records(DATASET)
    return next(r for r in records if len(technical_paragraphs(r)) > CAP)


def _single(expected) -> IssueItem:
    return IssueItem(
        title="Technical Language",
        description=f"Uses {expected.anchor}.",
        severity="low",
        start_line=expected.line,
        end_line=expected.line,
    )


def _summary(
    rest, title="Technical Language: Further Paragraphs", severity="low"
) -> IssueItem:
    return IssueItem(
        title=title,
        description="; ".join(
            f"line {e.line}: {e.anchor}, in plain words ..." for e in rest
        ),
        severity=severity,
        start_line=min(e.line for e in rest),
        end_line=max(e.line for e in rest),
    )


def test_overflow_passes_the_first_fifteen_plus_one_summary():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    issues = [_single(e) for e in paragraphs[:CAP]] + [_summary(paragraphs[CAP:])]
    values, _ = overflow_scores(issues, inventory)
    assert values == {key: 1.0 for key in OVERFLOW_KEYS}


def test_overflow_fails_a_run_that_reports_every_paragraph_on_its_own():
    inventory = _overflow_inventory()
    values, _ = overflow_scores(
        [_single(e) for e in technical_paragraphs(inventory)], inventory
    )
    assert values["overflow_cap"] == 0.0 and values["overflow_summary_title"] == 0.0
    assert values["overflow_summary_covers_rest"] == 0.0


def test_overflow_fails_a_run_that_keeps_the_wrong_fifteen():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    # The last 15 kept, the first two summarized: under the cap, but not the first in document order.
    issues = [_single(e) for e in paragraphs[2:]] + [_summary(paragraphs[:2])]
    values, explanation = overflow_scores(issues, inventory)
    assert values["overflow_cap"] == 1.0 and values["overflow_first_in_order"] == 0.0
    assert values["overflow_summary_covers_rest"] == 0.0
    assert paragraphs[0].id in explanation


def test_overflow_fails_one_broad_issue_standing_for_several_paragraphs():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    first, rest = paragraphs[:CAP], paragraphs[CAP:]
    broad = _single(first[0])
    broad.end_line = first[1].line
    # 14 issues for 15 paragraphs: the broad one covers the first two but can own only one.
    issues = [broad] + [_single(e) for e in first[2:]] + [_summary(rest)]
    values, explanation = overflow_scores(issues, inventory)
    assert values["overflow_first_in_order"] == 0.0
    assert first[1].id in explanation or first[0].id in explanation


def test_overflow_fails_a_single_issue_on_a_paragraph_past_the_cap():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    first, rest = paragraphs[:CAP], paragraphs[CAP:]
    issues = [_single(e) for e in first] + [_single(rest[0]), _summary(rest)]
    values, explanation = overflow_scores(issues, inventory)
    assert values["overflow_first_in_order"] == 0.0
    assert rest[0].id in explanation


def test_overflow_fails_a_summary_with_the_wrong_title_severity_or_range():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    first, rest = paragraphs[:CAP], paragraphs[CAP:]
    wrong_title, _ = overflow_scores(
        [_single(e) for e in first]
        + [_summary(rest, title="Technical Language: Summary")],
        inventory,
    )
    assert wrong_title["overflow_summary_title"] == 0.0
    wrong_severity, _ = overflow_scores(
        [_single(e) for e in first] + [_summary(rest, severity="medium")], inventory
    )
    assert (
        wrong_severity["overflow_summary_title"] == 0.0
        and wrong_severity["overflow_summary_covers_rest"] == 1.0
    )
    short = _summary(rest)
    short.end_line = rest[0].line
    too_short, _ = overflow_scores([_single(e) for e in first] + [short], inventory)
    assert too_short["overflow_summary_covers_rest"] == 0.0


def test_overflow_is_not_scored_on_other_samples():
    records = load_inventory_records(DATASET)
    ordinary = next(r for r in records if 0 < len(technical_paragraphs(r)) <= CAP)
    values, _ = overflow_scores([], ordinary)
    assert all(math.isnan(v) for v in values.values())


class _Completion:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _Grader:
    """Grades C unless the prompt's paragraph contains ``failing``; keeps the prompts it saw."""

    def __init__(self, failing: str = "") -> None:
        self.failing = failing
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> _Completion:
        self.prompts.append(prompt)
        paragraph = prompt.split("[Paragraph]: ", 1)[1].split("\n", 1)[0]
        failed = self.failing and self.failing in paragraph
        return _Completion("GRADE: I" if failed else "GRADE: C")


@pytest.mark.asyncio
async def test_overflow_judge_grades_the_summary_once_per_remaining_paragraph():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    rest = paragraphs[CAP:]
    issues = [_single(e) for e in paragraphs[:CAP]] + [_summary(rest)]
    grader = _Grader()
    values, _ = await summary_alternative_scores(cast(Model, grader), issues, inventory)
    assert values == {SUMMARY_KEY: 1.0}
    assert len(grader.prompts) == len(rest)
    lines = inventory.document.split("\n")
    for prompt, e in zip(grader.prompts, rest):
        assert f"[Paragraph]: {lines[e.line - 1]}" in prompt
        assert f"[Technical term in the paragraph]: {e.anchor}" in prompt


@pytest.mark.asyncio
async def test_overflow_judge_fails_a_summary_missing_one_alternative():
    inventory = _overflow_inventory()
    paragraphs = technical_paragraphs(inventory)
    rest = paragraphs[CAP:]
    issues = [_single(e) for e in paragraphs[:CAP]] + [_summary(rest)]
    grader = _Grader(failing=rest[-1].anchor)
    values, explanation = await summary_alternative_scores(
        cast(Model, grader), issues, inventory
    )
    assert values == {SUMMARY_KEY: 0.5}
    assert rest[-1].id in explanation


@pytest.mark.asyncio
async def test_overflow_judge_scores_zero_without_a_single_summary_and_nan_elsewhere():
    inventory = _overflow_inventory()
    grader = _Grader()
    values, _ = await summary_alternative_scores(
        cast(Model, grader),
        [_single(e) for e in technical_paragraphs(inventory)],
        inventory,
    )
    assert values == {SUMMARY_KEY: 0.0} and grader.prompts == []
    records = load_inventory_records(DATASET)
    ordinary = next(r for r in records if 0 < len(technical_paragraphs(r)) <= CAP)
    values, _ = await summary_alternative_scores(cast(Model, grader), [], ordinary)
    assert math.isnan(values[SUMMARY_KEY])
