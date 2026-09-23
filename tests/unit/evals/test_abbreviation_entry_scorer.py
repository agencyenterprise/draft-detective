import json
from types import SimpleNamespace

import pytest
from inspect_ai.scorer import Target

from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import (
    AbbreviationCheckOutput,
    AbbreviationItem,
    _compare_abbreviation_list,
    _compare_abbreviation_occurrences,
    _pooled_occurrence_counts,
    single_entry_scorer,
)


def test_occurrence_number_drift_does_not_fail_a_line_match():
    expected = {
        "abbr": "1PL",
        "inline_definition": "one-parameter logistic model",
        "occurrence_number": 5,
        "line_start": 493,
        "line_end": 493,
        "abbreviations_section_definition": "one-parameter logistic model",
        "ignored": False,
        "ignored_reason": None,
    }
    actual = AbbreviationItem(**{**expected, "occurrence_number": 4})

    matched, errors, additional = _compare_abbreviation_occurrences(
        [expected], [actual]
    )

    assert matched == 1
    assert errors == []
    assert additional == []


def test_pooled_occurrence_counts_uses_tp_fp_fn_metadata():
    class Score:
        metadata = {
            "TOTAL": 11,
            "TP": 4,
            "FP": 6,
            "FN": 1,
        }

    class SampleScore:
        score = Score()

    assert _pooled_occurrence_counts([SampleScore()]) == (4, 6, 1)


def occurrence(**kwargs):
    return AbbreviationItem(
        abbr="AI", occurrence_number=1, line_start=1, line_end=1, **kwargs
    )


def test_shifted_ordinal_does_not_override_exact_annotation_match():
    defined = occurrence(inline_definition="artificial intelligence")
    bare = occurrence()
    expected = [defined.model_dump(), {**bare.model_dump(), "occurrence_number": 2}]
    actual = [bare, defined.model_copy(update={"occurrence_number": 2})]
    matched, errors, extras = _compare_abbreviation_occurrences(expected, actual)
    assert matched == 2
    assert not errors and not extras


def test_document_scorer_cannot_reuse_one_prediction_for_two_occurrences():
    item = occurrence()
    state = SimpleNamespace(metadata={"target_abbreviations": [item.model_dump()] * 2})
    score = _compare_abbreviation_list(
        AbbreviationCheckOutput(abbreviations=[item]), state
    )
    assert score.value == 0.5


def test_incorrect_earlier_reference_does_not_consume_later_exact_match():
    bare = occurrence()
    defined = occurrence(inline_definition="artificial intelligence")
    matched, errors, extra = _compare_abbreviation_occurrences(
        [defined.model_dump(), bare.model_dump()], [bare]
    )
    assert matched == 1
    assert [error["type"] for error in errors] == ["missing_occurrence"]
    assert not extra


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_definition", [False, True])
async def test_score_agrees_with_counts_including_document_extras(
    tmp_path, wrong_definition
):
    expected = occurrence(inline_definition="artificial intelligence")
    actual = (
        expected.model_copy(update={"inline_definition": "wrong"})
        if wrong_definition
        else expected
    )
    unknown = actual.model_copy(update={"abbr": "XYZ"})
    refs = tmp_path / "references.json"
    refs.write_text(json.dumps({"test.md": {"abbreviations": [expected.model_dump()]}}))
    state = SimpleNamespace(
        metadata={"reference_file": str(refs), "filename": "test.md"},
        output=SimpleNamespace(
            completion=AbbreviationCheckOutput(
                abbreviations=[actual, unknown]
            ).model_dump_json()
        ),
    )
    score = await single_entry_scorer()(
        state, Target(json.dumps([expected.model_dump()]))
    )
    counts = score.metadata
    assert counts["FP"] == (2 if wrong_definition else 1)
    assert counts["FN"] == int(wrong_definition)
    assert counts["TOTAL"] == counts["TP"] + counts["FP"] + counts["FN"]
    assert score.value == counts["TP"] / counts["TOTAL"]
    assert "document-wide unknown" in score.explanation
