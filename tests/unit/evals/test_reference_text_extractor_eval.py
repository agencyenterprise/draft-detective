"""The Reference Extraction eval: its dataset, its task, and its set-matching scorer."""

import math
from pathlib import Path

import pytest
import yaml

from evals_inspectai.common.loaders import resolve_input
from evals_inspectai.e2e.reference_text_extractor.criteria import (
    KEYS,
    ExtractedReference,
    reference_scores,
)
from evals_inspectai.e2e.reference_text_extractor.matching import DocumentText, compact, match
from evals_inspectai.e2e.reference_text_extractor.records import (
    ReferenceRecord,
    not_in_document,
    record_to_sample,
)
from evals_inspectai.e2e.reference_text_extractor.reference_text_extractor_e2e import (
    reference_text_extractor_e2e,
)

DATASET = Path("evals_inspectai/e2e/reference_text_extractor/dataset.yaml")
RECORDS = [ReferenceRecord.model_validate(r) for r in yaml.safe_load(DATASET.read_text())]

CLEAN_DOC = "# Introduction\n\nNo references here (Smith, 2020).\n"
DOC = (
    "## References\n\n"
    "1. Smith, J. (2020). The Effects of Widgets. Journal of Widgetry.\n"
    "2. Doe, A. (2019). A Study of Gizmos. Gizmo Press.\n"
    "3. Roe, B. (2017). Cellphones and Writing. Journal of Big Tech.\n"
)
EXPECTED = [
    "Smith, J. (2020). The Effects of Widgets. Journal of Widgetry.",
    "Doe, A. (2019). A Study of Gizmos. Gizmo Press.",
    "Roe, B. (2017). Cellphones and Writing. Journal of Big Tech.",
]


def refs(*texts: str, lines: tuple[int, int] | None = None) -> list[ExtractedReference]:
    start, end = lines or (None, None)
    return [ExtractedReference(text=t, start_line=start, end_line=end) for t in texts]


def placed(texts: list[str], first_line: int) -> list[ExtractedReference]:
    return [ExtractedReference(text=t, start_line=first_line + k, end_line=first_line + k) for k, t in enumerate(texts)]


# --- dataset ---------------------------------------------------------------


def test_dataset_is_well_formed():
    assert len(RECORDS) == 16
    assert all(r.notes for r in RECORDS), "every record says why it exists"
    assert sum(1 for r in RECORDS if not r.target_references) == 3
    assert [len(r.target_references) for r in RECORDS if r.input.startswith("file://")] == [152, 309]
    assert sum(len(r.optional_references) for r in RECORDS) == 2


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r.input[:40])
def test_every_expected_reference_is_the_documents_text(record: ReferenceRecord):
    document = resolve_input(record.input)
    assert not_in_document(record.target_references + record.optional_references, document) == []


def test_expected_references_follow_the_skill():
    for record in RECORDS:
        for text in record.target_references:
            assert text == " ".join(text.split()), "one line, single spaces"
            assert not text.startswith(("---", "———", "___", "- ", "* ", "[")), text
            assert "&amp;" not in text and "\xa0" not in text


def test_loader_refuses_a_label_the_document_does_not_contain():
    raw = {"input": DOC, "target_references": ["Invented, X. (2024). Not in the list."], "notes": "bad"}
    with pytest.raises(ValueError, match="not found"):
        record_to_sample(raw)


# --- task ------------------------------------------------------------------


def test_task_composition():
    t = reference_text_extractor_e2e()
    assert len(t.dataset) == 16 and len(t.scorer) == 1
    assert list(t.metadata["metrics"]["reference_checks"]) == list(KEYS)
    assert t.viewer is not None
    columns = [c.id for c in t.viewer.task_samples_view.columns]
    assert all(f"score__reference_checks__{key}" in columns for key in KEYS)
    sample = t.dataset[0]
    assert sample.metadata is not None and set(sample.metadata) == {"target_references", "optional_references", "notes"}


# --- normalization and matching ------------------------------------------


def test_normalization_evens_out_conversion_noise():
    assert compact("Smith &amp; Doe, Vol.\xa030,  research\\_reports ’x’") == compact("Smith & Doe, Vol. 30, research_reports 'x'")


def test_document_check_allows_list_markers_and_resolved_placeholders():
    text = DocumentText(["- Anthropic. 2025a. 'First.' As of 3", "- December 2025: https://a.example", "- ---. 2025b. 'Second Title Here.'"])
    assert text.contains("Anthropic. 2025a. 'First.' As of 3 December 2025: https://a.example")
    assert text.contains("Anthropic. 2025b. 'Second Title Here.'")
    assert not text.contains("Anthropic. 2026. 'Third Title Not There.'")


WORKS_CITED = [
    "## Works Cited",
    "",
    "Thompson, R. & Davis, K. (2022). Transformer Models for Clinical Text Understanding. Journal of Biomedical Informatics, 125, 103967.",
    "",
    "---. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA.",
    "",
    "Chen, Y., Liu, H. (2023). Deep Learning Methods. Radiology, 306(2), 412-425.",
]


def test_a_placeholder_resolves_only_to_the_previous_entrys_author():
    text = DocumentText(WORKS_CITED)
    assert text.contains("Thompson, R. & Davis, K. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA.")
    assert not text.contains("Invented, X. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA.")
    assert not text.contains("Chen, Y., Liu, H. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA.")


def test_adjacent_entries_joined_together_are_not_the_documents_text():
    text = DocumentText(WORKS_CITED)
    assert not text.contains(
        "Thompson, R. & Davis, K. (2022). Transformer Models for Clinical Text Understanding. Journal of Biomedical "
        "Informatics, 125, 103967. Chen, Y., Liu, H. (2023). Deep Learning Methods."
    )
    assert not text.contains("JAMIA. Chen, Y., Liu, H. (2023). Deep Learning Methods.")
    # Hanging-indent lists put each entry on its own line with no blank line between.
    hanging = DocumentText(["Adams, B. (2019). First Title. Press.", "Baker, C. (2020). Second Title. Press."])
    assert hanging.contains("Adams, B. (2019). First Title. Press.")
    assert not hanging.contains("Adams, B. (2019). First Title. Press. Baker, C. (2020). Second Title. Press.")


def test_a_wrapped_entry_and_a_split_url_stay_one_entry():
    text = DocumentText([
        "Health Office, 'Serum Repository,' webpage, last updated July 22, 2024. As of May 5, 2025:",
        "",
        "https://www.health.example/Topics/AFHSD/",
        "",
        "Functional-Support/Serum-Repository",
        "",
        "Ivers, P. (2021). A Title That Wraps",
        "Onto the Next Line. Journal, 3(1), 1-9. doi: 10.1000/xyz",
        "Jones, Q. (2022). Next Entry. Press.",
    ])
    assert text.contains(
        "Health Office, 'Serum Repository,' webpage, last updated July 22, 2024. As of May 5, 2025: "
        "https://www.health.example/Topics/AFHSD/Functional-Support/Serum-Repository"
    )
    assert text.contains("Ivers, P. (2021). A Title That Wraps Onto the Next Line. Journal, 3(1), 1-9. doi: 10.1000/xyz")
    assert not text.contains("doi: 10.1000/xyz Jones, Q. (2022). Next Entry. Press.")


def test_a_line_range_check_resolves_a_placeholder_from_outside_the_range():
    text = DocumentText(WORKS_CITED)
    resolved = "Thompson, R. & Davis, K. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA."
    assert text.contains(resolved, 5, 5), "the author on line 3 is outside the range but still resolves the placeholder"
    assert not text.contains(resolved, 7, 7)
    assert not text.contains("Invented, X. (2023). Large-Scale EHR Mining: Methods and Applications. JAMIA.", 5, 5)


def test_matching_is_one_to_one_and_prefers_identical_texts():
    expected = ["Smith, J. (2020). Widgets. Journal.", "Smith, J. (2020). Widgets. Journal, 2nd ed."]
    pairs = match(["Smith, J. (2020). Widgets. Journal.", "Smith, J. (2020). Widgets. Journal."], expected)
    assert sorted(pairs) == [(0, 0), (1, 1)]


# --- scorer: the cases DeepDiff got wrong ---------------------------------


def test_invented_reference_on_a_clean_document_fails_clean_and_precision():
    values, explanation = reference_scores(refs("Smith, J. (2020). A Paper."), [], [], CLEAN_DOC)
    assert values["clean_document_untouched"] == 0.0 and values["precision"] == 0.0
    assert values["verbatim_in_document"] == 0.0
    assert math.isnan(values["recall"]) and math.isnan(values["f1"]) and math.isnan(values["text_exact"])
    assert "extra 1" in explanation and "not verbatim 1" in explanation


def test_nothing_extracted_on_a_clean_document_passes():
    values, _ = reference_scores([], [], [], CLEAN_DOC)
    assert values["clean_document_untouched"] == 1.0
    assert all(math.isnan(values[k]) for k in KEYS if k != "clean_document_untouched")


def test_junk_references_cost_precision_not_recall():
    junk = ["Methods overview.", "Figure 1. Widgets over time.", "See the appendix for details."]
    values, explanation = reference_scores(refs(*EXPECTED, *junk), EXPECTED, [], DOC)
    assert values["recall"] == 1.0 and values["precision"] == 0.5
    assert values["f1"] == pytest.approx(2 / 3)
    assert values["verbatim_in_document"] == 0.5
    assert "extra 3" in explanation


def test_whitespace_only_differences_are_matched_and_exact():
    spaced = [f"  {t.replace(' ', chr(0xA0), 2)}  " for t in EXPECTED]
    values, _ = reference_scores(placed(spaced, 3), EXPECTED, [], DOC)
    assert values["recall"] == values["precision"] == values["text_exact"] == 1.0
    assert values["verbatim_in_document"] == values["lines_bracket_text"] == 1.0


def test_tolerant_matches_are_found_but_not_exact():
    texts = [EXPECTED[0].rstrip("."), "1. " + EXPECTED[1], EXPECTED[2]]
    values, explanation = reference_scores(refs(*texts), EXPECTED, [], DOC)
    assert values["recall"] == values["precision"] == 1.0
    assert values["text_exact"] == pytest.approx(1 / 3)
    assert "inexact 2" in explanation


def test_merged_references_miss_both():
    values, _ = reference_scores(refs(EXPECTED[0] + " " + EXPECTED[1], EXPECTED[2]), EXPECTED, [], DOC)
    assert values["recall"] == pytest.approx(1 / 3) and values["precision"] == 0.5


def test_optional_references_are_neither_required_nor_penalised():
    optional = ["Doe, A. (2019). A Study of Gizmos. Gizmo Press."]
    required = [EXPECTED[0], EXPECTED[2]]
    with_it, _ = reference_scores(refs(*EXPECTED), required, optional, DOC)
    without_it, _ = reference_scores(refs(EXPECTED[0], EXPECTED[2]), required, optional, DOC)
    assert with_it["precision"] == without_it["precision"] == 1.0
    assert with_it["recall"] == without_it["recall"] == 1.0


def test_lines_must_hold_the_text():
    good, _ = reference_scores(placed(EXPECTED, 3), EXPECTED, [], DOC)
    shifted, explanation = reference_scores(placed(EXPECTED, 4), EXPECTED, [], DOC)
    assert good["lines_bracket_text"] == 1.0
    assert shifted["lines_bracket_text"] == 0.0 and "lines do not hold the text 3" in explanation
    unplaced, _ = reference_scores(refs(*EXPECTED), EXPECTED, [], DOC)
    assert math.isnan(unplaced["lines_bracket_text"])


def test_every_key_is_emitted():
    values, _ = reference_scores(refs(*EXPECTED), EXPECTED, [], DOC)
    assert tuple(values) == KEYS
