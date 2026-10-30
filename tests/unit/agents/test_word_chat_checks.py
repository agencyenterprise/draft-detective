"""Tests for the checks the Word add-in's chat lists.

Run against the real skills and workflow registry, because the point is which of them
reach the list: only workflows, and only ones that can run without the internet.
"""

from lib.agents.word_chat_checks import pane_checks
from lib.workflows.registry import get_all_manifests


def listed() -> dict[str, object]:
    return {check.skill: check for check in pane_checks()}


def test_checks_that_need_the_internet_are_left_out() -> None:
    checks = listed()

    for skill in ("reference-validation", "methodology-comparison", "citation-support"):
        assert skill not in checks, skill
    assert "literature-review" not in checks


def test_only_workflows_are_listed_not_helper_skills() -> None:
    checks = listed()

    assert "abbreviation-scan" in checks
    for helper in ("issues", "voice-and-tone", "capabilities", "reference-extraction"):
        assert helper not in checks, helper


def test_each_check_is_named_and_described_like_the_workflow_picker() -> None:
    names = {manifest.name for manifest in get_all_manifests().values()}
    checks = pane_checks()

    assert len({check.name for check in checks}) == len(checks), "names are unique"
    for check in checks:
        assert check.description
        assert check.name in names


def test_stable_checks_come_before_experimental_ones() -> None:
    flags = [check.experimental for check in pane_checks()]

    assert flags == sorted(flags)


def test_retired_checks_are_left_out() -> None:
    """Structural Checks (GER) replaced the About This and Document Contents checks."""

    checks = listed()

    assert "structural-checks-ger" in checks
    for skill in ("about-this-authors", "about-this-preface", "document-contents"):
        assert skill not in checks, skill
