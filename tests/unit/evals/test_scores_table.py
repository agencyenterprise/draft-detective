"""Tests for the rules that turn a recorded run into its eval-scores row."""

import pytest

from evals_inspectai import scores_table
from evals_inspectai.scores_table import (
    ROW,
    RunSummary,
    describe,
    metric_kind,
    row_text,
)


def test_scorers_are_counted_as_judged_by_their_name():
    assert metric_kind("judged_criteria") == "judged"
    assert metric_kind("overflow_judge") == "judged"
    assert metric_kind("methodology_judged") == "judged"
    assert metric_kind("rubric_criteria") == "judged"
    assert metric_kind("input_identification") == "identification"
    # A deterministic metric's name may say "identified"; the scorer decides.
    assert metric_kind("plant_checks") == "deterministic"


def test_the_spread_reads_as_a_range_a_single_value_or_all():
    assert describe("deterministic", [0.955, 1.0, 1.0]) == "3 deterministic 0.955–1.000"
    assert describe("judged", [1.0, 1.0]) == "2 judged all 1.000"
    assert describe("judged", [0.887]) == "1 judged 0.887"


def test_a_generated_row_is_read_back_by_the_row_pattern():
    run = RunSummary(
        task="figures_tables_check",
        samples=33,
        epochs=3,
        scorers="20 deterministic 0.955–1.000",
        overall=0.98765,
        created="2026-11-05",
    )
    log = (
        "2026-11-05T20-41-02-00-00_figures-tables-check-e2e_mh2r6zEcG5ufgXaeRqfKT6.eval"
    )
    line = row_text("7", "figures_tables_check", "[^figures_tables_check]", log, run)

    match = ROW.match(line)
    assert match is not None
    assert (match["num"], match["name"], match["log"]) == (
        "7",
        "figures_tables_check",
        log,
    )
    assert "| **0.988** | 2026-11-05 |" in line


def _row(name: str, log: str) -> str:
    run = RunSummary(
        task=name,
        samples=1,
        epochs=3,
        scorers="1 deterministic 1.000",
        overall=1.0,
        created="2026-11-05",
    )
    return row_text("1", name, "", log, run)


def test_recording_is_planned_before_any_file_is_touched(monkeypatch, tmp_path):
    """A log with no row stops the recording before anything is copied or deleted."""
    tasks = {"good.eval": "figures_tables_check", "stray.eval": "no_such_eval"}
    monkeypatch.setattr(
        scores_table,
        "summarize",
        lambda log: RunSummary(
            task=tasks[log.name],
            samples=1,
            epochs=3,
            scorers="",
            overall=1.0,
            created="2026-11-05",
        ),
    )
    lines = [_row("figures_tables_check", "old_figures-tables-check-e2e_A.eval")]

    planned = scores_table.plan_recording([tmp_path / "good.eval"], lines)
    assert planned.replaced == ["old_figures-tables-check-e2e_A.eval"]
    assert "good.eval" in planned.lines[0]
    assert lines[0].endswith("old_figures-tables-check-e2e_A.eval) |")

    with pytest.raises(SystemExit):
        scores_table.plan_recording(
            [tmp_path / "good.eval", tmp_path / "stray.eval"], lines
        )
