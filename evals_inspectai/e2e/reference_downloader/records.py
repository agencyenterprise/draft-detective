"""Ground truth and checks for the Reference Downloader eval.

A single expected conclusion cannot tell a run that downloaded the cited work
from one that downloaded something else and called it found, and several
references can fairly end two ways (a paywalled article with an open copy, a
homepage cited as of a past date). So each record accepts a set of conclusions
and names two sets of phrases: `file_terms`, from the work's own title, which
say the kept file is the cited work, and `end_terms`, from the last part of the
work, which say it is the whole of it rather than a preview of its first pages.

The phrases are checked by the solver, against the file the app kept, read from
the project's file listing, rather than taken on the agent's word. Only the
verdicts are stored in the log, never the file's text, since the downloaded
works include paywalled articles and books and the logs under ``docs/evals/``
are published.
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
        default_factory=list, description="Phrases of the work's own title a downloaded file of it must contain"
    )
    end_terms: list[str] = Field(
        default_factory=list,
        description=(
            "Phrases from the last part of the work (its final section, references or back cover) that a "
            "complete copy contains and a preview of its first pages does not"
        ),
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
    """A file of the project as the app lists it, with the solver's verdicts on its text in
    place of the text itself (see ``text_checks``)."""

    id: str
    role: str
    file_name: str = ""
    chars: int = 0
    title_found: Optional[bool] = None
    end_found: Optional[bool] = None


class DownloaderOutput(BaseModel):
    """The workflow state, plus the project's files the solver read back."""

    fetched_references: list[FetchResult] = Field(default_factory=list)
    project_files: list[ProjectFile] = Field(default_factory=list)


KEYS = (
    "conclusion_accepted",
    "file_kept_when_found",
    "file_matches_reference",
    "file_complete",
    "no_file_when_not_found",
    "reason_when_inaccessible",
    "url_when_found",
)


def loose_text(text: str) -> str:
    """Normalised text with hyphens read as spaces, so "bow-tie" matches "bow tie"."""
    return " ".join(normalize(text).replace("-", " ").replace("‐", " ").split())


def text_checks(record: DownloadRecord, markdown: str) -> tuple[Optional[bool], Optional[bool]]:
    """Whether a file's text carries every ``file_terms`` phrase and every ``end_terms``
    phrase; None for a set the record leaves empty."""
    text = loose_text(markdown)

    def carries(terms: Sequence[str]) -> Optional[bool]:
        return all(loose_text(t) in text for t in terms) if terms else None

    return carries(record.file_terms), carries(record.end_terms)


def kept_file(item: FetchItem, files: Sequence[ProjectFile]) -> Optional[ProjectFile]:
    """The supporting file the run names as the source, if the project keeps it."""
    return next((f for f in files if item.file_id and f.id == item.file_id and f.role == KEPT_ROLE), None)


def _verdict(found: Optional[bool], applies: bool) -> float:
    return float(found) if applies and found is not None else math.nan


def download_scores(item: FetchItem, files: Sequence[ProjectFile], record: DownloadRecord) -> tuple[dict[str, float], str]:
    """Every key in ``KEYS`` for one reference.

    ``file_kept_when_found``: a found source names a file the project keeps as a
    supporting document. ``file_matches_reference``: that file carries every
    ``file_terms`` phrase. ``file_complete``: it carries every ``end_terms`` phrase.
    ``no_file_when_not_found``: any other conclusion keeps no supporting file and names
    none (a leftover candidate file is not visible through the app's listing, see
    ``KEPT_ROLE``). ``reason_when_inaccessible``: a found-but-not-accessible source says
    why. ``url_when_found``: a found source gives its URL. Each is NaN when the
    conclusion, or a record without such phrases, makes it moot."""
    found = item.final_conclusion == FOUND
    downloaded = [f for f in files if f.role == KEPT_ROLE]
    kept = kept_file(item, files)
    values = {
        "conclusion_accepted": float(item.final_conclusion in record.conclusion),
        "file_kept_when_found": float(kept is not None) if found else math.nan,
        "file_matches_reference": _verdict(kept.title_found if kept else None, found),
        "file_complete": _verdict(kept.end_found if kept else None, found),
        "no_file_when_not_found": math.nan if found else float(not downloaded and not item.file_id),
        "reason_when_inaccessible": float(bool((item.inaccessibility_reason or "").strip())) if item.final_conclusion == NOT_ACCESSIBLE else math.nan,
        "url_when_found": float(bool((item.source_url or "").strip())) if found else math.nan,
    }
    notes = [f"concluded {item.final_conclusion}, expected {'/'.join(record.conclusion)}"] if not values["conclusion_accepted"] else []
    notes += [f"file {item.file_id} is not a kept supporting file"] if found and kept is None else []
    notes += [f"the kept file lacks the title phrases {record.file_terms} ({kept.file_name})"] if kept and kept.title_found is False else []
    notes += [f"the kept file lacks the end phrases {record.end_terms}: a preview or partial copy ({kept.file_name}, {kept.chars} characters)"] if kept and kept.end_found is False else []
    notes += [f"{len(downloaded)} supporting file(s) kept"] if not found and downloaded else []
    notes += [f"file {item.file_id} named"] if not found and item.file_id else []
    notes += ["no reason given for the inaccessible source"] if values["reason_when_inaccessible"] == 0.0 else []
    notes += ["no source URL for the found source"] if values["url_when_found"] == 0.0 else []
    return values, " | ".join(notes) if notes else "outcome and file as expected"


DESCRIPTIONS = {
    "conclusion_accepted": "1 if the conclusion is one the record accepts (found, found but not accessible, not found).",
    "file_kept_when_found": "On source_found, 1 if the named file is among the project's supporting files. NaN otherwise.",
    "file_matches_reference": "On source_found with a kept file, 1 if its text contains every phrase the record takes from the work's title. NaN otherwise.",
    "file_complete": "On source_found with a kept file, 1 if its text contains every phrase the record takes from the last part of the work, so the file is the whole work rather than a preview of its first pages. NaN otherwise, or when the record names none.",
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
