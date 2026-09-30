"""The Reference Downloader eval: its dataset, the solver's text checks and the scores of the kept file."""

import json
import math
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from inspect_ai.model import ModelName
from inspect_ai.solver import TaskState

from evals_inspectai.e2e.reference_downloader import reference_downloader_e2e as task_module
from evals_inspectai.e2e.reference_downloader.records import (
    DownloadRecord,
    FetchItem,
    ProjectFile,
    download_scores,
    load_records,
    loose_text,
    text_checks,
)
from evals_inspectai.e2e.reference_downloader.reference_downloader_e2e import (
    project_file_summary,
    reference_downloader_e2e,
    reference_downloader_solver,
)

DATASET = Path("evals_inspectai/e2e/reference_downloader/dataset.yaml")
RECORD = DownloadRecord(
    id="aramis",
    reference="de Dianous ... ARAMIS Project: A More Explicit Demonstration of Risk Control ...",
    conclusion=["source_found", "source_found_but_not_accessible"],
    file_terms=["More Explicit Demonstration of Risk Control"],
    end_terms=["References"],
)
MAIN = ProjectFile(id="m", role="main", file_name="eval-document.md")
ARTICLE = "ARAMIS Project: A More Explicit Demonstration of Risk Control ... 5. Conclusion ... References 1. ..."
PREVIEW = "ARAMIS Project: A More Explicit Demonstration of Risk Control ... pages 220-224 ... Download to read the full document."


def _kept(title_found: bool = True, end_found: bool = True) -> ProjectFile:
    return ProjectFile(id="f1", role="support", file_name="aramis.pdf", chars=60_000, title_found=title_found, end_found=end_found)


def _found(**kw: str) -> FetchItem:
    return FetchItem(**{"final_conclusion": "source_found", "file_id": "f1", "source_url": "https://x.org/aramis.pdf", **kw})


def test_dataset_is_well_formed():
    records = load_records(DATASET)
    assert len(records) == 35
    assert all(r.file_terms for r in records if "source_found" in r.conclusion)
    assert sum(1 for r in records if r.end_terms) == 28


def test_file_terms_come_from_the_citation_and_identify_it():
    """A term is a phrase of the work's own title, and no other record's citation carries all of
    a record's terms, so a different downloaded work cannot pass for this one on a shared topic."""
    records = [r for r in load_records(DATASET) if r.file_terms]
    for record in records:
        assert all(loose_text(t) in loose_text(record.reference) for t in record.file_terms), record.id
        others = [o.id for o in records if o.id != record.id and all(loose_text(t) in loose_text(o.reference) for t in record.file_terms)]
        assert not others, (record.id, others)


def test_task_has_the_download_checks():
    t = reference_downloader_e2e()
    assert len(t.dataset) == 35 and len(t.metadata["metrics"]["download_checks"]) == 7


def test_the_text_checks_tell_a_complete_copy_from_a_preview():
    assert text_checks(RECORD, ARTICLE) == (True, True)
    assert text_checks(RECORD, PREVIEW) == (True, False)
    assert text_checks(RECORD, "A different paper on risk.") == (False, False)
    assert text_checks(RECORD.model_copy(update={"end_terms": []}), ARTICLE) == (True, None)


def test_a_listed_file_is_reduced_to_its_verdicts():
    summary = project_file_summary(RECORD, {"id": "f1", "role": "support", "file_name": "aramis.md", "markdown": PREVIEW})
    assert summary == {"id": "f1", "role": "support", "file_name": "aramis.md", "chars": len(PREVIEW), "title_found": True, "end_found": False}


def test_a_found_source_is_checked_against_the_kept_file():
    values, note = download_scores(_found(), [MAIN, _kept()], RECORD)
    assert values["conclusion_accepted"] == values["file_kept_when_found"] == values["file_matches_reference"] == values["file_complete"] == 1.0
    assert math.isnan(values["no_file_when_not_found"]) and math.isnan(values["reason_when_inaccessible"])
    assert note == "outcome and file as expected"


def test_a_preview_kept_as_the_source_fails_completeness():
    values, note = download_scores(_found(), [MAIN, _kept(end_found=False)], RECORD)
    assert values["file_matches_reference"] == 1.0 and values["file_complete"] == 0.0
    assert "lacks the end phrases" in note and "60000 characters" in note


def test_a_found_source_whose_file_is_another_work_fails():
    values, note = download_scores(_found(), [MAIN, _kept(title_found=False)], RECORD)
    assert values["file_matches_reference"] == 0.0 and "lacks the title phrases" in note
    values, note = download_scores(_found(), [MAIN], RECORD)
    assert values["file_kept_when_found"] == 0.0 and math.isnan(values["file_matches_reference"]) and math.isnan(values["file_complete"])


def test_completeness_is_unscored_for_a_record_without_end_phrases():
    kept = ProjectFile(id="f1", role="support", chars=900, title_found=True, end_found=None)
    values, _ = download_scores(_found(), [MAIN, kept], RECORD.model_copy(update={"end_terms": []}))
    assert math.isnan(values["file_complete"])


def test_a_found_source_without_a_url_is_named_in_the_explanation():
    values, note = download_scores(_found(source_url=""), [MAIN, _kept()], RECORD)
    assert values["url_when_found"] == 0.0 and "no source URL" in note


def test_an_inaccessible_source_needs_a_reason_and_keeps_no_file():
    item = FetchItem(final_conclusion="source_found_but_not_accessible")
    stray = ProjectFile(id="f2", role="support", file_name="preview.html")
    values, note = download_scores(item, [MAIN, stray], RECORD)
    assert values["no_file_when_not_found"] == 0.0 and values["reason_when_inaccessible"] == 0.0
    assert "kept" in note and "no reason" in note
    named = FetchItem(final_conclusion="source_not_found", file_id="f3")
    values, note = download_scores(named, [MAIN], RECORD)
    assert values["no_file_when_not_found"] == 0.0 and "named" in note


@pytest.mark.asyncio
async def test_the_solver_keeps_verdicts_and_no_downloaded_text():
    state = TaskState(ModelName("none/none"), sample_id="aramis", epoch=1, input=RECORD.reference, messages=[], metadata={"record": RECORD.model_dump()})
    listing = [{"id": "m", "role": "main", "file_name": "eval-document.md", "markdown": "## References"}, {"id": "f1", "role": "support", "file_name": "aramis.md", "markdown": PREVIEW}]
    run = {"state": {"fetched_references": [{"result": {"final_conclusion": "source_found", "file_id": "f1"}}]}, "run": {"id": "r"}}
    with (
        patch.object(task_module, "create_project_and_start_workflows", AsyncMock(return_value="p1")),
        patch.object(task_module, "start_workflow", AsyncMock(return_value="r")),
        patch.object(task_module, "poll_workflow_run_until_complete", AsyncMock(return_value=run)),
        patch.object(task_module, "get_project_files", AsyncMock(return_value=listing)),
    ):
        state = await reference_downloader_solver()(state, AsyncMock())
    output = json.loads(state.output.completion)
    assert "pages 220-224" not in state.output.completion
    assert output["project_files"][1] == {"id": "f1", "role": "support", "file_name": "aramis.md", "chars": len(PREVIEW), "title_found": True, "end_found": False}
