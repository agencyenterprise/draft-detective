"""Unit tests for building annotation items from eval datasets and scoring agreement."""

from pathlib import Path

import pytest
import yaml

from evals_inspectai.common.issue_inventory import normalize
from lib.models.annotation import AnnotationItemKind
from lib.services.annotations.admin import agrees_with_reference
from lib.services.annotations.catalog import ANNOTATION_SETS, SHOULD_FLAG, ACTIVE_VOICE
from lib.services.annotations.eval_items import items_from_inventory
from lib.services.annotations.service import validate_answers


@pytest.mark.parametrize("spec", ANNOTATION_SETS, ids=lambda s: s.slug)
def test_catalog_sets_build_valid_items(spec):
    drafts = items_from_inventory(spec)

    assert drafts, f"{spec.slug} produced no items"
    assert len({d.source_key for d in drafts}) == len(drafts)
    for draft in drafts:
        assert normalize(draft.passage.anchor) in normalize(draft.passage.document)
        assert draft.passage.line is not None
        validate_answers(draft.reference_answers, spec.questions)


@pytest.mark.parametrize("spec", ANNOTATION_SETS, ids=lambda s: s.slug)
def test_every_decoy_reason_has_a_plain_reading(spec):
    reasons = {
        decoy["reason"]
        for record in yaml.safe_load(spec.dataset_path.read_text())
        for decoy in record.get("decoys", [])
    }
    assert reasons <= set(spec.decoy_reasons), sorted(reasons - set(spec.decoy_reasons))


def test_items_skip_passages_without_a_single_answer(tmp_path: Path):
    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(
        yaml.safe_dump(
            [
                {
                    "input": "Data were collected by the team.\n\nWe surveyed staff.\n\nFunds were cut.\n\nNurses were eligible.",
                    "expected_issues": [
                        {
                            "title": "Passive Voice",
                            "anchor": "Data were collected by the team",
                        },
                        {
                            "title": "Passive Voice",
                            "anchor": "Funds were cut",
                            "required": False,
                        },
                    ],
                    "decoys": [
                        {"anchor": "We surveyed staff", "reason": "active"},
                        {
                            "anchor": "Nurses were eligible",
                            "reason": "stative",
                            "title": "Passive Voice",
                        },
                    ],
                }
            ]
        )
    )

    drafts = items_from_inventory(ACTIVE_VOICE, dataset)

    assert [
        (d.kind, d.passage.anchor, d.reference_answers[SHOULD_FLAG]) for d in drafts
    ] == [
        (AnnotationItemKind.EXPECTED_ISSUE, "Data were collected by the team", "yes"),
        (AnnotationItemKind.DECOY, "We surveyed staff", "no"),
    ]
    assert drafts[0].passage.line == 1
    assert drafts[1].passage.line == 3
    assert "“Passive Voice”" in (drafts[0].reference_explanation or "")
    assert "already active" in (drafts[1].reference_explanation or "")


def test_source_key_changes_with_the_document(tmp_path: Path):
    def keys(document: str) -> list[str]:
        dataset = tmp_path / "dataset.yaml"
        record = {
            "input": document,
            "decoys": [{"anchor": "We surveyed staff", "reason": "active"}],
        }
        dataset.write_text(yaml.safe_dump([record]))
        return [d.source_key for d in items_from_inventory(ACTIVE_VOICE, dataset)]

    assert keys("We surveyed staff.") == keys("We surveyed staff.")
    assert keys("We surveyed staff.") != keys("We surveyed staff in May.")


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("yes", True), ("no", False), ("unsure", None)],
)
def test_agreement_with_reference(answer, expected):
    questions = ACTIVE_VOICE.questions
    assert (
        agrees_with_reference({SHOULD_FLAG: answer}, {SHOULD_FLAG: "yes"}, questions)
        is expected
    )


@pytest.mark.parametrize(
    "answers",
    [{}, {SHOULD_FLAG: "maybe"}, {SHOULD_FLAG: "yes", "extra": "no"}],
)
def test_validate_answers_rejects_incomplete_or_unknown(answers):
    with pytest.raises(ValueError):
        validate_answers(answers, ACTIVE_VOICE.questions)
