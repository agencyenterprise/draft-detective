"""The Reference Downloader eval: its dataset and its checks of the kept file."""

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest
from inspect_ai.model import ModelName, ModelOutput
from inspect_ai.scorer import Target
from inspect_ai.solver import TaskState

from evals_inspectai.e2e.reference_downloader import reference_downloader_e2e as task_module
from evals_inspectai.e2e.reference_downloader.records import (
    DownloadRecord,
    FetchItem,
    ProjectFile,
    completeness_prompt,
    download_scores,
    load_records,
)
from evals_inspectai.e2e.reference_downloader.reference_downloader_e2e import download_judged, reference_downloader_e2e

DATASET = Path("evals_inspectai/e2e/reference_downloader/dataset.yaml")
RECORD = DownloadRecord(id="aramis", reference="de Dianous ... ARAMIS ...", conclusion=["source_found", "source_found_but_not_accessible"], file_terms=["ARAMIS", "bow-tie"])
MAIN = ProjectFile(id="m", role="main", file_name="eval-document.md", markdown="## References")


def test_dataset_is_well_formed():
    records = load_records(DATASET)
    assert len(records) == 35
    assert all(r.file_terms for r in records if "source_found" in r.conclusion)


def test_task_has_the_download_checks():
    t = reference_downloader_e2e()
    assert len(t.dataset) == 35 and len(t.metadata["metrics"]["download_checks"]) == 6
    assert len(t.scorer) == 2 and set(t.metadata["metrics"]["download_judged"]) == {"file_is_complete"}


def test_a_found_source_is_checked_against_the_kept_file():
    item = FetchItem(final_conclusion="source_found", file_id="f1", source_url="https://x.org/aramis.pdf")
    kept = ProjectFile(id="f1", role="support", file_name="aramis.pdf", markdown="# ARAMIS project\n\nBow tie diagrams ...")
    values, _ = download_scores(item, [MAIN, kept], RECORD)
    assert values["conclusion_accepted"] == values["file_kept_when_found"] == values["file_matches_reference"] == 1.0
    assert math.isnan(values["no_file_when_not_found"]) and math.isnan(values["reason_when_inaccessible"])


def test_a_found_source_whose_file_is_another_work_fails():
    item = FetchItem(final_conclusion="source_found", file_id="f1", source_url="https://x.org")
    other = ProjectFile(id="f1", role="support", file_name="other.pdf", markdown="A different paper on risk.")
    values, note = download_scores(item, [MAIN, other], RECORD)
    assert values["file_matches_reference"] == 0.0 and "lacks" in note
    values, note = download_scores(item, [MAIN], RECORD)
    assert values["file_kept_when_found"] == 0.0 and math.isnan(values["file_matches_reference"])


def test_an_inaccessible_source_needs_a_reason_and_keeps_no_file():
    item = FetchItem(final_conclusion="source_found_but_not_accessible")
    stray = ProjectFile(id="f2", role="support", file_name="preview.html")
    values, note = download_scores(item, [MAIN, stray], RECORD)
    assert values["no_file_when_not_found"] == 0.0 and values["reason_when_inaccessible"] == 0.0
    assert "kept" in note and "no reason" in note
    named = FetchItem(final_conclusion="source_not_found", file_id="f3")
    values, note = download_scores(named, [MAIN], RECORD)
    assert values["no_file_when_not_found"] == 0.0 and "named" in note



PREVIEW = ProjectFile(
    id="f1",
    role="support",
    file_name="aramis.md",
    markdown="# ARAMIS project\n\nPages 220-224 of the bow-tie article ...",
    markdown_tail="... Download to read the full document. Subscribe to Scribd for unlimited access.",
    markdown_chars=41_200,
)


def test_the_completeness_grader_sees_the_files_end_and_length():
    prompt = completeness_prompt(RECORD, PREVIEW)
    assert "Subscribe to Scribd" in prompt and "41200 characters" in prompt and "Pages 220-224" in prompt


def test_a_short_file_is_shown_whole_without_its_images():
    page = ProjectFile(id="p", role="support", file_name="post.md", markdown="Headline ![logo](https://x.org/a.png) body text.", markdown_chars=48)
    prompt = completeness_prompt(RECORD, page)
    assert "[Text of the file]: Headline [image] body text." in prompt and "a.png" not in prompt


def test_a_phrase_near_the_end_of_the_file_counts_for_the_file_terms():
    record = RECORD.model_copy(update={"file_terms": ["Subscribe to Scribd"]})
    item = FetchItem(final_conclusion="source_found", file_id="f1", source_url="https://x.org")
    values, _ = download_scores(item, [MAIN, PREVIEW], record)
    assert values["file_matches_reference"] == 1.0


class _Completion:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _Grader:
    def __init__(self, grade: str) -> None:
        self.grade = grade
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> _Completion:
        self.prompts.append(prompt)
        return _Completion(f"It is a preview.\n\nGRADE: {self.grade}")


def _state(conclusion: str, files: list[ProjectFile]) -> TaskState:
    state = TaskState(ModelName("none/none"), sample_id="aramis", epoch=1, input=RECORD.reference, messages=[], metadata={"record": RECORD.model_dump()})
    fetch = {"final_conclusion": conclusion, "file_id": "f1" if conclusion == "source_found" else None, "source_url": "https://x.org"}
    completion = {"fetched_references": [{"result": fetch}], "project_files": [f.model_dump() for f in files]}
    state.output = ModelOutput.from_content(model="none", content=json.dumps(completion))
    return state


@pytest.mark.asyncio
async def test_a_preview_kept_as_the_source_fails_completeness():
    grader = _Grader("I")
    with patch.object(task_module, "get_model", return_value=grader):
        score = await download_judged()(_state("source_found", [MAIN, PREVIEW]), Target(""))
    assert score.value == {"file_is_complete": 0.0} and score.explanation == "It is a preview."
    assert len(grader.prompts) == 1


@pytest.mark.asyncio
async def test_completeness_is_unscored_without_a_kept_file():
    grader = _Grader("C")
    with patch.object(task_module, "get_model", return_value=grader):
        score = await download_judged()(_state("source_found_but_not_accessible", [MAIN]), Target(""))
    assert isinstance(score.value, dict) and math.isnan(score.value["file_is_complete"]) and not grader.prompts
