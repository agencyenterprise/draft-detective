"""The Reference Downloader eval: its dataset and its checks of the kept file."""

import math
from pathlib import Path

from evals_inspectai.e2e.reference_downloader.records import DownloadRecord, FetchItem, ProjectFile, download_scores, load_records
from evals_inspectai.e2e.reference_downloader.reference_downloader_e2e import reference_downloader_e2e

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
