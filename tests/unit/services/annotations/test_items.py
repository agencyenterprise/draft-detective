"""Unit tests for building annotation items from eval datasets and scoring agreement."""

from pathlib import Path

import pytest
import yaml

from evals_inspectai.common.issue_inventory import normalize
from lib.models.annotation import AnnotationItemKind
from lib.services.annotations.admin import agrees_with_reference
from lib.services.annotations.catalog import ANNOTATION_SETS
from lib.services.annotations.eval_items import items_from_inventory
from lib.services.annotations.service import validate_answers
from lib.services.annotations.set_spec import SHOULD_FLAG
from lib.services.annotations.sets.active_voice import ACTIVE_VOICE
from lib.services.annotations.sets.inference_validation_v2 import INFERENCE_VALIDATION
from lib.services.annotations.sets.recommendation_check import RECOMMENDATION_CHECK


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


def _write(tmp_path: Path, record: dict) -> Path:
    dataset = tmp_path / "dataset.yaml"
    dataset.write_text(yaml.safe_dump([record]))
    return dataset


def test_single_kind_sets_keep_decoys_titled_with_that_kind(tmp_path: Path):
    dataset = _write(
        tmp_path,
        {
            "input": "Sales rose after the ad ran, so the ad caused it.\n\nIn this sample, sales rose.",
            "expected_issues": [
                {
                    "title": "Invalid Inference",
                    "anchor": "so the ad caused it",
                    "rationale": "Post hoc reasoning.",
                }
            ],
            "decoys": [
                {
                    "anchor": "In this sample, sales rose",
                    "reason": "bounded_claim",
                    "title": "Invalid Inference",
                }
            ],
        },
    )

    drafts = items_from_inventory(INFERENCE_VALIDATION, dataset)

    assert [d.reference_answers[SHOULD_FLAG] for d in drafts] == ["yes", "no"]
    assert (drafts[0].reference_explanation or "").endswith("Post hoc reasoning.")


def test_recommendations_are_flagged_unless_fully_supported(tmp_path: Path):
    dataset = _write(
        tmp_path,
        {
            "input": "\n\n".join(
                [
                    "Loans grew 38 percent.",
                    "1. Grow the e-book budget.",
                    "2. Cap meetings at six hours.",
                    "3. Replace the terminals.",
                    "4. Hire staff.",
                ]
            ),
            "expected_issues": [
                {"anchor": "Grow the e-book budget", "severity": "none"},
                {"anchor": "Cap meetings at six hours", "severity": "medium"},
                {"anchor": "Replace the terminals", "severity": "high"},
                {"anchor": "Hire staff"},
                {
                    "id": "hire_not_actionable",
                    "anchor": "Hire staff",
                    "title": "Recommendation Not Actionable",
                    "severity": "medium",
                },
            ],
            "decoys": [
                {"anchor": "Loans grew 38 percent", "reason": "conclusion"},
                {
                    "anchor": "Grow the e-book budget",
                    "reason": "single_actor",
                    "title": "Recommendation Audience Unclear",
                },
            ],
        },
    )

    drafts = items_from_inventory(RECOMMENDATION_CHECK, dataset)

    assert [
        (d.kind, d.passage.anchor, d.reference_answers[SHOULD_FLAG]) for d in drafts
    ] == [
        (AnnotationItemKind.EXPECTED_ISSUE, "Grow the e-book budget", "no"),
        (AnnotationItemKind.EXPECTED_ISSUE, "Cap meetings at six hours", "yes"),
        (AnnotationItemKind.EXPECTED_ISSUE, "Replace the terminals", "yes"),
        (AnnotationItemKind.DECOY, "Loans grew 38 percent", "no"),
    ]
    assert "as supported" in (drafts[0].reference_explanation or "")


def test_items_carry_the_documents_figures_inline():
    drafts = items_from_inventory(INFERENCE_VALIDATION)
    with_figures = [d for d in drafts if "![" in d.passage.document]

    assert with_figures
    for draft in with_figures:
        assert "](files/" not in draft.passage.document
        assert "data:image/png;base64," in draft.passage.document


def test_source_key_changes_with_a_figure(tmp_path: Path, monkeypatch):
    dataset = _write(
        tmp_path,
        {
            "input": "We surveyed staff.\n\n![](files/figures/chart.png)",
            "decoys": [{"anchor": "We surveyed staff", "reason": "active"}],
        },
    )

    def key_with(figure: str) -> str:
        monkeypatch.setattr(
            "lib.services.annotations.eval_items.inline_local_images",
            lambda markdown: markdown.replace("files/figures/chart.png", figure),
        )
        return items_from_inventory(ACTIVE_VOICE, dataset)[0].source_key

    assert key_with("data:image/png;base64,AAAA") == key_with(
        "data:image/png;base64,AAAA"
    )
    assert key_with("data:image/png;base64,AAAA") != key_with(
        "data:image/png;base64,BBBB"
    )


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
