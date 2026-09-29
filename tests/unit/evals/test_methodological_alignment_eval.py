"""The Methodological Alignment eval: its dataset, its deterministic checks, and the judged loop with a scripted grader."""

import math
from pathlib import Path
from typing import cast

import pytest
from inspect_ai.model import Model

from evals_inspectai.common.issue_inventory import Decoy, InventoryRecord, ExpectedIssue, load_inventory_records, resolve_record
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.methodological_alignment.criteria import REQUIRED_SECTIONS, decoy_prompt, report_scores
from evals_inspectai.e2e.methodological_alignment.methodological_alignment_e2e import (
    judge_methodology,
    methodological_alignment_e2e,
    plant_scores,
)

DATASET = Path("evals_inspectai/e2e/methodological_alignment/dataset.yaml")
DOC = (
    "# Study\n\n## Methods\n\n"
    "Teams self-selected into the treatment.\n\n"
    "We used cluster-robust standard errors by team.\n\n"
    "No correction for multiple comparisons was applied.\n"
)
INVENTORY = resolve_record(
    InventoryRecord(
        input=DOC,
        expected_issues=[
            ExpectedIssue(id="selection", anchor="Teams self-selected", severity="high", rationale="Randomize or use DiD."),
            ExpectedIssue(id="multiplicity", anchor="No correction for multiple comparisons", rationale="Correct with Holm."),
        ],
        decoys=[Decoy(anchor="cluster-robust standard errors", reason="clustered_se", rationale="Standard for team assignment.")],
    )
)


def _issue(title: str, line: int, severity: str = "high", action: str = "Randomize the teams.") -> IssueItem:
    return IssueItem(title=title, description=title, severity=severity, start_line=line, end_line=line, suggested_action=action)


class _Completion:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _Grader:
    """Answers I for prompts containing any of ``fail_on``, C otherwise, and keeps the prompts."""

    def __init__(self, *fail_on: str) -> None:
        self.fail_on = fail_on
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> _Completion:
        self.prompts.append(prompt)
        return _Completion("GRADE: I" if any(f in prompt for f in self.fail_on) else "GRADE: C")


def test_dataset_is_well_formed():
    records = load_inventory_records(DATASET)
    assert len(records) == 10
    assert all(2 <= len(r.expected_issues) <= 4 and r.decoys for r in records)
    assert all(e.anchor and e.rationale and e.severity in (None, "high") for r in records for e in r.expected_issues)
    assert all(d.rationale for r in records for d in r.decoys), "a judged decoy carries the labeller's reason"


def test_task_has_the_report_plant_and_judged_scorers():
    t = methodological_alignment_e2e()
    assert len(t.dataset) == 10 and len(t.scorer) == 3
    assert set(t.metadata["metrics"]) == {"report_checks", "plant_checks", "methodology_judged"}


def test_report_checks_name_missing_sections_and_informational_issues():
    report = "\n".join(f"## {s}\n\nText." for s in REQUIRED_SECTIONS[:4]) + "\n\nSee [a guide](https://example.org)."
    values, note = report_scores(report, [_issue("Methodology: A", 5), _issue("Methodology: B", 5, severity="none")])
    assert values == {"report_sections": 0.8, "report_cites_links": 1.0, "no_informational": 0.5}
    assert "Suggestions for Improvements" in note and "informational" in note


def test_plants_are_covered_by_any_issue_on_their_line_at_a_fitting_severity():
    values, note = plant_scores([_issue("Methodology: Self-selection", 5, severity="low")], INVENTORY)
    assert values["recall"] == 0.5 and values["anchor_in_range"] == 1.0 and values["severity_fits"] == 0.0
    assert "multiplicity" in note and "reported low" in note


@pytest.mark.asyncio
async def test_the_best_issue_on_a_plants_line_names_it_and_its_action_is_graded():
    issues = [
        _issue("Methodology: Proxy measure", 5),  # another gap on the plant's line
        _issue("Methodology: Self-selection", 5),
        _issue("Methodology: Clustered errors unjustified", 7),
    ]
    grader = _Grader("Methodology: Proxy measure\n\n")
    values, note = await judge_methodology(cast(Model, grader), issues, INVENTORY)
    assert values["gap_identified"] == 0.5, "self-selection named by the second issue; multiplicity has nothing on its line"
    assert values["action_repairs"] == 1.0
    assert values["sound_choices_respected"] == 1.0
    assert "multiplicity gap_identified 0.0: nothing on its line" in note


@pytest.mark.asyncio
async def test_a_criticised_sound_choice_fails_and_no_named_plant_leaves_actions_unscored():
    grader = _Grader("Proxy", "[Reviewer's issues]")
    values, _ = await judge_methodology(cast(Model, grader), [_issue("Methodology: Proxy", 5)], INVENTORY)
    assert values["gap_identified"] == 0.0 and math.isnan(values["action_repairs"])
    assert values["sound_choices_respected"] == 0.0


def test_the_sound_choice_grader_sees_every_field_of_every_issue():
    issue = IssueItem(
        title="Methodology: Errors",
        description="About inference.",
        long_description="Cluster-robust errors with three teams are unreliable.",
        suggested_action="Use a wild-cluster bootstrap.",
        severity="high",
        start_line=7,
        end_line=7,
    )
    prompt = decoy_prompt(INVENTORY.decoys[0], [issue], DOC)
    assert "Cluster-robust errors with three teams are unreliable." in prompt and "wild-cluster bootstrap" in prompt
