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
from pathlib import Path
from typing import Literal, Optional, Sequence

import yaml
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict, Field, field_validator

from evals_inspectai.common.issue_inventory import normalize

Conclusion = Literal["source_found", "source_found_but_not_accessible", "source_not_found"]
FOUND = "source_found"
NOT_ACCESSIBLE = "source_found_but_not_accessible"

# Roles of the files the downloader adds; the uploaded document is `main`.
DOWNLOADED_ROLES = ("support", "supporting_candidate")


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
    """A file of the project as the app lists it, markdown trimmed by the solver."""

    id: str
    role: str
    file_name: str = ""
    markdown: str = ""


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


def _loose(text: str) -> str:
    """Normalised text with hyphens read as spaces, so "bow-tie" matches "bow tie"."""
    return " ".join(normalize(text).replace("-", " ").replace("‐", " ").split())


def download_scores(item: FetchItem, files: Sequence[ProjectFile], record: DownloadRecord) -> tuple[dict[str, float], str]:
    """Every key in ``KEYS`` for one reference.

    ``file_kept_when_found``: a found source names a file the project keeps as a
    supporting document. ``file_matches_reference``: that file's text carries every
    ``file_terms`` phrase. ``no_file_when_not_found``: any other conclusion leaves no
    downloaded file behind. ``reason_when_inaccessible``: a found-but-not-accessible
    source says why. ``url_when_found``: a found source gives its URL. Each is NaN
    when the conclusion makes it moot."""
    found = item.final_conclusion == FOUND
    downloaded = [f for f in files if f.role in DOWNLOADED_ROLES]
    kept = next((f for f in files if item.file_id and f.id == item.file_id and f.role == "support"), None)
    text = _loose(kept.markdown) if kept else ""
    absent = [t for t in record.file_terms if _loose(t) not in text]
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
    notes += [f"{len(downloaded)} downloaded file(s) left behind"] if not found and downloaded else []
    notes += ["no reason given for the inaccessible source"] if values["reason_when_inaccessible"] == 0.0 else []
    return values, " | ".join(notes) if notes else "outcome and file as expected"


DESCRIPTIONS = {
    "conclusion_accepted": "1 if the conclusion is one the record accepts (found, found but not accessible, not found).",
    "file_kept_when_found": "On source_found, 1 if the named file is among the project's supporting files. NaN otherwise.",
    "file_matches_reference": "On source_found with a kept file, 1 if its text contains every phrase the record names from the work. NaN otherwise.",
    "no_file_when_not_found": "On any other conclusion, 1 if no downloaded file is left in the project and no file is named. NaN on source_found.",
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
