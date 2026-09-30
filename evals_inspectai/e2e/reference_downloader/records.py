"""Ground truth and checks for the Reference Downloader eval.

A single expected conclusion cannot tell a run that downloaded the cited work
from one that downloaded something else and called it found, and several
references can fairly end two ways (a paywalled article with an open copy, a
homepage cited as of a past date). So each record accepts a set of conclusions
and names phrases the downloaded file must contain, and the checks read the
file the app kept, from the project's file listing, rather than the agent's own
report of it.
"""

import math
import re
from pathlib import Path
from typing import Literal, Optional, Sequence

import yaml
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict, Field, field_validator

from evals_inspectai.common.issue_inventory import normalize
from evals_inspectai.common.issue_judge import issue_prompt_from

Conclusion = Literal["source_found", "source_found_but_not_accessible", "source_not_found"]
FOUND = "source_found"
NOT_ACCESSIBLE = "source_found_but_not_accessible"

# The role a kept download has. The app's file listing shows only main, support and
# reviewer-memo files, so a transient `supporting_candidate` left behind by cleanup is not
# visible to the eval, which reads the project through the same endpoint as the app.
KEPT_ROLE = "support"


class DownloadRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    reference: str
    conclusion: list[Conclusion] = Field(description="Conclusions a correct run may reach")
    file_terms: list[str] = Field(
        default_factory=list, description="Phrases a downloaded file of this work must contain"
    )
    notes: Optional[str] = None

    @field_validator("conclusion", mode="before")
    @classmethod
    def _one_or_many(cls, value: object) -> object:
        return [value] if isinstance(value, str) else value


class FetchItem(BaseModel):
    """Local mirror of ReferenceFetchItem."""

    final_conclusion: str = ""
    source_url: Optional[str] = None
    file_id: Optional[str] = None
    inaccessibility_reason: Optional[str] = None
    reasoning: str = ""


class FetchResult(BaseModel):
    reference_id: str = ""
    input_reference: str = ""
    status: str = ""
    result: Optional[FetchItem] = None
    error: Optional[str] = None


class ProjectFile(BaseModel):
    """A file of the project as the app lists it, its markdown trimmed by the solver to the
    opening and the end, with the full length kept."""

    id: str
    role: str
    file_name: str = ""
    markdown: str = ""
    markdown_tail: str = ""
    markdown_chars: int = 0


class DownloaderOutput(BaseModel):
    """The workflow state, plus the project's files the solver read back."""

    fetched_references: list[FetchResult] = Field(default_factory=list)
    project_files: list[ProjectFile] = Field(default_factory=list)


KEYS = (
    "conclusion_accepted",
    "file_kept_when_found",
    "file_matches_reference",
    "no_file_when_not_found",
    "reason_when_inaccessible",
    "url_when_found",
)


def loose_text(text: str) -> str:
    """Normalised text with hyphens read as spaces, so "bow-tie" matches "bow tie"."""
    return " ".join(normalize(text).replace("-", " ").replace("‐", " ").split())


def kept_file(item: FetchItem, files: Sequence[ProjectFile]) -> Optional[ProjectFile]:
    """The supporting file the run names as the source, if the project keeps it."""
    return next((f for f in files if item.file_id and f.id == item.file_id and f.role == KEPT_ROLE), None)


def download_scores(item: FetchItem, files: Sequence[ProjectFile], record: DownloadRecord) -> tuple[dict[str, float], str]:
    """Every key in ``KEYS`` for one reference.

    ``file_kept_when_found``: a found source names a file the project keeps as a
    supporting document. ``file_matches_reference``: that file's text carries every
    ``file_terms`` phrase. ``no_file_when_not_found``: any other conclusion keeps no
    supporting file and names none (a leftover candidate file is not visible through the
    app's listing, see ``KEPT_ROLE``). ``reason_when_inaccessible``: a found-but-not-accessible
    source says why. ``url_when_found``: a found source gives its URL. Each is NaN
    when the conclusion makes it moot."""
    found = item.final_conclusion == FOUND
    downloaded = [f for f in files if f.role == KEPT_ROLE]
    kept = kept_file(item, files)
    text = loose_text(f"{kept.markdown} {kept.markdown_tail}") if kept else ""
    absent = [t for t in record.file_terms if loose_text(t) not in text]
    values = {
        "conclusion_accepted": float(item.final_conclusion in record.conclusion),
        "file_kept_when_found": float(kept is not None) if found else math.nan,
        "file_matches_reference": float(not absent) if found and kept and record.file_terms else math.nan,
        "no_file_when_not_found": math.nan if found else float(not downloaded and not item.file_id),
        "reason_when_inaccessible": float(bool((item.inaccessibility_reason or "").strip())) if item.final_conclusion == NOT_ACCESSIBLE else math.nan,
        "url_when_found": float(bool((item.source_url or "").strip())) if found else math.nan,
    }
    notes = [f"concluded {item.final_conclusion}, expected {'/'.join(record.conclusion)}"] if not values["conclusion_accepted"] else []
    notes += [f"file {item.file_id} is not a kept supporting file"] if found and kept is None else []
    notes += [f"the downloaded file lacks {absent} ({kept.file_name})"] if found and kept and absent else []
    notes += [f"{len(downloaded)} supporting file(s) kept"] if not found and downloaded else []
    notes += [f"file {item.file_id} named"] if not found and item.file_id else []
    notes += ["no reason given for the inaccessible source"] if values["reason_when_inaccessible"] == 0.0 else []
    notes += ["no source URL for the found source"] if values["url_when_found"] == 0.0 else []
    return values, " | ".join(notes) if notes else "outcome and file as expected"


DESCRIPTIONS = {
    "conclusion_accepted": "1 if the conclusion is one the record accepts (found, found but not accessible, not found).",
    "file_kept_when_found": "On source_found, 1 if the named file is among the project's supporting files. NaN otherwise.",
    "file_matches_reference": "On source_found with a kept file, 1 if its text contains every phrase the record names from the work. NaN otherwise.",
    "no_file_when_not_found": "On any other conclusion, 1 if the project keeps no supporting file and no file is named (a leftover candidate file is not visible through the app's file listing). NaN on source_found.",
    "reason_when_inaccessible": "On source_found_but_not_accessible, 1 if a reason is given. NaN otherwise.",
    "url_when_found": "On source_found, 1 if the source URL is given. NaN otherwise.",
}


def load_records(path: Path) -> list[DownloadRecord]:
    records = [DownloadRecord.model_validate(r) for r in yaml.safe_load(path.read_text())]
    if len({r.id for r in records}) != len(records):
        raise ValueError(f"{path}: record ids repeat")
    return records


def download_dataset(records: list[DownloadRecord], path: Path) -> MemoryDataset:
    return MemoryDataset(
        samples=[Sample(id=r.id, input=r.reference, metadata={"record": r.model_dump()}) for r in records],
        name=path.parent.name,
        location=str(path),
    )


# Markdown image syntax, stripped from what the grader reads: a scraped page is full of
# image links, and the grader must judge the text, not fetch pictures.
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

COMPLETENESS_CRITERION = (
    "A downloader was asked for the full original content of a cited work and kept the file shown. A separate check "
    "confirms it is the cited work, so do not judge which work it is: grade only whether the file holds the whole of "
    "it. A saved web page normally carries site navigation, headers, footers, cookie notices and link lists around "
    "the content; they are not a sign that anything is missing, and a homepage, database page or listing page is "
    "complete when the cited page's own content is there. A PDF that ends with references, an appendix, a table or "
    "a page number is complete. It is correct if the work's content is all there, or nothing shows otherwise. It is "
    "partially correct only with clear evidence that a small part of the work is missing (a page or a closing "
    "section lost in conversion). It is incorrect if the file is a preview or excerpt, however genuine the pages it "
    "shows (the first pages of a longer work followed by prompts to subscribe, log in or download the rest, or far "
    "fewer pages than the reference's page range), a one-page document that visibly breaks off, an abstract or summary "
    "in place of the work, a table of contents, an error or blocked page, or holds almost no text."
)


def _clean(text: str) -> str:
    return _IMAGE_RE.sub("[image]", text)


def completeness_prompt(record: DownloadRecord, kept: ProjectFile) -> str:
    """The grader reads all the text the solver kept: the file's opening (up to the solver's
    cap), and its end when the file runs past the cap, so a preview's closing prompts and a
    web page's article are both in view."""
    length = kept.markdown_chars or len(kept.markdown)
    blocks = [("Text of the file" if length <= len(kept.markdown) else "Opening of the file", _clean(kept.markdown) or "(empty)")]
    if length > len(kept.markdown) and kept.markdown_tail:
        blocks.append(("End of the file", _clean(kept.markdown_tail)))
    return issue_prompt_from(
        COMPLETENESS_CRITERION,
        [("Reference", record.reference), ("Kept file", f"{kept.file_name} ({length} characters of text)"), *blocks],
    )


JUDGE_DESCRIPTIONS = {
    "file_is_complete": "On source_found with a kept file, graded from the file's opening, end and length: the file is the complete work, not a preview, excerpt, abstract or landing page (C=1, P=0.5, I=0). NaN otherwise.",
}
