"""InventorySuite: one policy derived from the dataset, carried to every scorer through the sample."""

import json
import math
from pathlib import Path

import pytest
from inspect_ai.model import ModelName, ModelOutput
from inspect_ai.scorer import Target
from inspect_ai.solver import TaskState

from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_checks import DETECTION_KEYS, EDIT_KEYS, hit_pairs, inventory_from_state
from evals_inspectai.common.simple_deep_agent_types import IssueItem

DOC = "# Title\n\nData were collected from 3 sites.\n\nFindings are listed in Appendix A.\n"
# One issue quoting both sentences: covers both expected issues when shared, only one when one-to-one.
MERGED = {"title": "Passive Voice", "description": "“Data were collected” and “Findings are listed”", "start_line": 3, "end_line": 5}


def _write(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "suite_case" / "dataset.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(records))  # JSON is YAML
    return path


def _two_expected(tmp_path: Path, **extra: object) -> Path:
    record = {
        "input": DOC,
        "expected_issues": [
            {"id": "first", "title": "Passive Voice", "anchor": "Data were collected"},
            {"id": "second", "title": "Passive Voice", "anchor": "Findings are listed"},
        ],
        **extra,
    }
    return _write(tmp_path, [record, {"input": "# Clean\n\nNothing here.\n", "decoys": [{"anchor": "Nothing here", "reason": "clean"}]}])


def _state(suite: InventorySuite, issues: list[dict]) -> TaskState:
    sample = suite.dataset()[0]
    return TaskState(
        model=ModelName("mockllm/model"), sample_id=1, epoch=1, input=sample.input, messages=[],
        output=ModelOutput(completion=json.dumps({"result": {"issues": issues}})), metadata=sample.metadata,
    )


def test_policy_is_derived_from_the_data_and_carried_on_every_record(tmp_path):
    suite = InventorySuite.load(_two_expected(tmp_path), pairing="one_to_one")
    policy = suite.policy
    assert policy.pairing == "one_to_one"
    assert policy.named_titles == ["Passive Voice"] and policy.decoy_reasons == ["clean"]
    assert not policy.edits and policy.titles and policy.anchors and not policy.severities
    assert all(r.policy == policy for r in suite.records)
    assert suite.name == "suite_case"


@pytest.mark.asyncio
@pytest.mark.parametrize(("pairing", "recall"), [("shared", 1.0), ("one_to_one", 0.5)])
async def test_the_scorer_reads_the_pairing_from_the_sample(tmp_path, pairing, recall):
    suite = InventorySuite.load(_two_expected(tmp_path), pairing=pairing)
    state = _state(suite, [MERGED])
    issue_checks = suite.scorers()[0]
    score = await issue_checks(state, Target(""))
    assert score.value["recall"] == recall
    # An eval's own criterion pairs the same way, from the same inventory.
    pairs = hit_pairs([IssueItem(**MERGED)], inventory_from_state(state))[1]
    assert len(pairs) == int(recall * 2)


@pytest.mark.asyncio
async def test_keys_follow_the_policy(tmp_path):
    suite = InventorySuite.load(_two_expected(tmp_path))
    score = await suite.scorers()[0](_state(suite, [MERGED]), Target(""))
    assert set(score.value) == set(DETECTION_KEYS) - {"severity_correct"}, "no edits or severities in the data"
    assert math.isnan(score.value["clean_document_untouched"])


def test_decoy_checks_only_when_the_dataset_has_decoys(tmp_path):
    path = _write(tmp_path, [{"input": DOC, "expected_issues": [{"title": "Missing Section: Methods"}]}])
    suite = InventorySuite.load(path)
    assert len(suite.scorers()) == 1
    assert "decoy_checks" not in suite.descriptions()
    assert InventorySuite.load(_two_expected(tmp_path)).descriptions()["decoy_checks"].keys() == {"no_fp_clean"}


def test_metadata_and_viewer_share_one_list_of_own_metrics(tmp_path):
    suite = InventorySuite.load(_two_expected(tmp_path))
    own = {"tone_checks": {"b": "B.", "a": "A."}, "judged_criteria": {"c": "C."}}
    metrics = suite.metadata("truth", own)["metrics"]
    assert list(metrics) == ["issue_checks", "decoy_checks", "tone_checks", "judged_criteria"]
    assert not set(metrics["issue_checks"]) & set(EDIT_KEYS)
    view = suite.viewer(own, {"a": "Label A"}).task_samples_view
    assert view is not None
    scored = [c.id.removeprefix("score__") for c in view.columns if c.id.startswith("score__")]
    generic = [f"issue_checks__{k}" for k in metrics["issue_checks"]] + ["decoy_checks__no_fp_clean"]
    assert scored == [*generic, "tone_checks__b", "tone_checks__a", "judged_criteria__c"]
    assert view.score_labels is not None and view.score_labels["a"] == "Label A" and view.score_labels["no_fp_clean"] == "No FP clean"


def test_extra_fields_are_split_off_and_mapped_to_sample_metadata(tmp_path):
    path = _two_expected(tmp_path, sources=[{"file_name": "a.md"}])
    with pytest.raises(ValueError, match="sources"):
        InventorySuite.load(path)  # an InventoryRecord forbids unknown fields
    suite = InventorySuite.load(path, extra_fields=("sources",))
    assert suite.extras == [{"sources": [{"file_name": "a.md"}]}, {}]
    samples = suite.dataset(lambda extra: {"n_sources": len(extra.get("sources", []))})
    assert [(s.metadata or {})["n_sources"] for s in samples] == [1, 0]
