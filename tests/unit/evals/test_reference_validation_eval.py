"""The Reference Validation eval: its per-field dataset and its deterministic checks."""

import math
from pathlib import Path

import pytest

from evals_inspectai.e2e.reference_validation_v2.criteria import (
    KEYS,
    FieldValidation,
    ValidationResult,
    mechanical_result,
    reasoning_prompt,
    validation_scores,
)
from evals_inspectai.e2e.reference_validation_v2.records import FIELDS, ReferenceRecord, load_records
from evals_inspectai.e2e.reference_validation_v2.reference_validation_v2_e2e import reference_validation_v2_e2e

DATASET = Path("evals_inspectai/e2e/reference_validation_v2/dataset.yaml")


def _result(final: str, url: str = "https://example.org", updated: str | None = None, **problems: str) -> ValidationResult:
    return ValidationResult(
        final_result=final,
        url=url,
        updated_reference=updated,
        bibliography_field_validations=[
            FieldValidation(category=f, problem_type=problems.get(f, "correct"), suggested_value=problems.get(f"{f}_value", ""))
            for f in FIELDS
        ],
    )


# Validated from a dict, as the YAML loader does, so a single value stands for a one-item list.
MISSPELLED = ReferenceRecord.model_validate(
    {
        "id": "misspelled",
        "reference": "Patel, Dylan, and Jeremie Elliahou Ontiveros, “AI Datacenter Energy,” SemiAnalysis, 2024.",
        "result": "incorrect_fields",
        "fields": {"author": "incorrect", "title": ["correct", "incorrect"]},
        "corrections": {"author": "Eliahou"},
        "rationale": "An author's surname is misspelled.",
    }
)


def test_dataset_is_well_formed():
    records = load_records(DATASET)
    assert len(records) == 80
    assert sum(r.not_found for r in records) == 6
    assert sum(1 for r in records if r.result == ["correct"] and not r.fields) == 47
    assert all(r.rationale for r in records if r.not_found or r.fields), "every labelled problem is explained"


def test_task_scores_every_check_and_the_reasoning():
    t = reference_validation_v2_e2e()
    assert len(t.dataset) == 80 and len(t.scorer) == 2
    assert set(t.metadata["metrics"]["validation_checks"]) == set(KEYS)


def test_a_correctly_flagged_reference_passes_every_check():
    result = _result("incorrect_fields", updated="Patel, Dylan, and Jeremie Eliahou Ontiveros ...", author="incorrect")
    values, note = validation_scores(result, MISSPELLED)
    assert all(v == 1.0 for v in values.values() if not math.isnan(v)), note


def test_the_wrong_field_flagged_fails_the_field_checks_but_not_the_result():
    result = _result("incorrect_fields", updated="Patel ...", year="incorrect")
    values, note = validation_scores(result, MISSPELLED)
    assert values["result_correct"] == 1.0
    assert values["flags_found"] == 0.0 and values["no_false_flags"] == pytest.approx(2 / 3)
    assert values["field_author"] == 0.0 and values["field_year"] == 0.0 and values["field_title"] == 1.0
    assert values["correction_given"] == 0.0 and "Eliahou" in note


def test_the_final_result_must_follow_from_the_fields():
    correct = ReferenceRecord(id="ok", reference="x")
    values, note = validation_scores(_result("incorrect_fields"), correct)
    assert values["result_follows_fields"] == 0.0 and "does not follow" in note
    assert mechanical_result(_result("x", publisher="missing")) == "missing_fields"
    assert mechanical_result(_result("x", publisher="missing", title="other")) == "incorrect_fields"


def test_a_fabricated_identifier_must_not_pass_as_correct():
    doi = ReferenceRecord(id="doi", reference="Smith, J. Avatars. IEEE TNNLS, 2021. doi: 10.1109/TNNLS.2021.3071234", not_found=True)
    url = ReferenceRecord(id="url", reference="Blog. (2024). A post. https://example.org/post", not_found=True)
    none = ReferenceRecord(id="none", reference="Doe, John. Widgets. 2020.", not_found=True)
    assert "correct" not in doi.accepted("identifier")
    assert url.accepted("identifier") == ["correct", "incorrect", "other"]
    assert none.accepted("identifier") == ["correct", "other"]
    values, note = validation_scores(_result("incorrect_fields", url="", author="incorrect", title="incorrect", publisher="incorrect", year="incorrect"), doi)
    assert values["field_identifier"] == 0.0 and "identifier: reported correct" in note


def test_a_fabricated_reference_gets_no_updated_reference_and_no_url_check():
    fabricated = ReferenceRecord(id="fake", reference="Doe, John. Widgets. 2020.", not_found=True)
    assert fabricated.result == ["incorrect_fields"] and fabricated.accepted("title") == ["incorrect", "other"]
    invented = _result("incorrect_fields", url="", updated="Doe, J. (2021). Gadgets.", author="incorrect", title="incorrect", publisher="other", year="other")
    values, note = validation_scores(invented, fabricated)
    assert values["updated_reference_as_specified"] == 0.0 and "where none belongs" in note
    assert math.isnan(values["url_when_found"]) and values["field_accuracy"] == 1.0


def test_a_bare_url_must_get_an_updated_reference():
    bare = ReferenceRecord.model_validate({"id": "url", "reference": "https://example.org/post", "result": "missing_fields", "fields": {f: "missing" for f in FIELDS}})
    assert bare.is_bare_url
    values, note = validation_scores(_result("missing_fields", author="missing"), bare)
    assert values["updated_reference_as_specified"] == 0.0 and "no updated reference" in note
    values, _ = validation_scores(_result("missing_fields", updated="Author. (2024). Post.", author="missing"), bare)
    assert values["updated_reference_as_specified"] == 1.0


def test_a_record_rejects_unknown_fields_and_labels_on_a_fabricated_reference():
    with pytest.raises(ValueError):
        ReferenceRecord.model_validate({"id": "x", "reference": "x", "fields": {"venue": "incorrect"}})
    with pytest.raises(ValueError):
        ReferenceRecord.model_validate({"id": "x", "reference": "x", "not_found": True, "fields": {"title": "incorrect"}})


def test_the_reasoning_prompt_carries_the_labellers_account_and_the_fields():
    prompt = reasoning_prompt(MISSPELLED, _result("incorrect_fields", author="incorrect"))
    assert "An author's surname is misspelled." in prompt and "- author: incorrect" in prompt


def test_a_fabricated_record_survives_a_round_trip_through_sample_metadata():
    fabricated = ReferenceRecord(id="fake", reference="Doe, John. Widgets. 2020.", not_found=True)
    assert ReferenceRecord.model_validate(fabricated.model_dump()) == fabricated


# Records that pin each rule the skill states, on both sides of it.
RULE_CASES = {
    "organization named once as author and publisher": (
        ["nerc_org_publisher", "joint_pub_1", "frontier_model_forum", "epa_filtration_facts", "rand_r322_org_author", "anthropic_author_date", "aphis_parent_publisher"],
        ["gallup_publisher_omitted", "crs_publisher_omitted"],
    ),
    "an omitted subtitle or deck that still identifies the work": (
        ["la_times_1991", "guardian_no_standfirst", "zero_days_no_subtitle"],
        ["ipcc_ambiguous_title"],
    ),
    # Fabricated references on one side; on the other, real works whose URL or identifier is
    # broken but whose title a search finds, which must be validated, not called fabricated.
    "a fabricated reference is not matched to a similar work": (
        ["nonexistent_google_saif", "nonexistent_claude_3_safety_case", "nonexistent_microsoft_blog"],
        ["semianalysis_misspelled_author", "dissanayake_wrong_doi", "gdpval_wrong_arxiv", "perficient_study"],
    ),
}


@pytest.mark.parametrize("rule", sorted(RULE_CASES))
def test_each_skill_rule_has_cases_on_both_sides(rule):
    """The rule's positive cases expect nothing flagged on the field it governs; its negative
    cases expect the flag the rule does not excuse."""
    records = {r.id: r for r in load_records(DATASET)}
    passing, failing = RULE_CASES[rule]
    assert passing and failing, "a rule needs cases on both sides"
    if rule.startswith("a fabricated"):
        assert all(records[r].not_found and records[r].result == ["incorrect_fields"] for r in passing)
        assert not any(records[r].not_found for r in failing), "a real work with a broken link is not fabricated"
        return
    for rid in passing:
        assert records[rid].result == ["correct"], rid
    for rid in failing:
        assert "correct" not in records[rid].result, rid
    if rule.startswith("organization"):
        assert all(records[r].accepted("publisher") == ["correct"] for r in passing)
        assert all(records[r].accepted("publisher") == ["missing"] for r in failing)
    if rule.startswith("an omitted subtitle"):
        assert all(records[r].accepted("title") == ["correct"] for r in passing)
        assert all("correct" not in records[r].accepted("title") for r in failing)
