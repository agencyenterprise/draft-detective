"""Discover full-document fixtures, preferring reviewable Markdown snapshots."""

import json
from pathlib import Path

from inspect_ai.dataset import Sample

SUPPORTED_EXTENSIONS = frozenset({".md", ".markdown", ".docx", ".doc", ".pdf"})


def document_files(directory: Path, filename: str | None = None) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"Missing fixture directory: {directory}")
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith("~$")
        and path.name.lower() != "readme.md"
    )
    if filename is not None:
        selected = [path for path in files if path.name == filename]
        if not selected:
            raise ValueError(f"No supported file named {filename!r} in {directory}")
        return selected
    # Retain legacy source files locally without evaluating both representations.
    preferred: dict[str, Path] = {}
    for path in files:
        if path.suffix.lower() in {".md", ".markdown"}:
            previous = preferred.get(path.stem)
            if previous is None or path.suffix.lower() == ".md":
                preferred[path.stem] = path
    return [
        path
        for path in files
        if path.stem not in preferred or path == preferred[path.stem]
    ]


def entry_samples(documents: list[Path], reference_path: Path) -> list[Sample]:
    """Build identical abbreviation rows for the agent and structured tasks."""
    if not documents:
        raise ValueError("No matching abbreviation documents")
    if not reference_path.is_file():
        raise ValueError(f"Missing abbreviation references: {reference_path}")
    refs = json.loads(reference_path.read_text(encoding="utf-8"))
    samples = []
    for document in documents:
        if document.name not in refs:
            raise ValueError(
                f"Missing reference for {document.name} in {reference_path}"
            )
        reference = refs[document.name]
        if reference.get("source_format", "markdown") != "markdown":
            raise ValueError(
                f"{document.name}: references must use Markdown line numbers"
            )
        groups: dict[str, list[dict]] = {}
        for entry in reference["abbreviations"]:
            if not entry.get("ignored", False):
                groups.setdefault(entry["abbr"], []).append(entry)
        if not groups:
            raise ValueError(
                f"{document.name}: no applicable reference abbreviations to score"
            )
        for abbr, entries in groups.items():
            samples.append(
                Sample(
                    id=f"{document.name}::{abbr}",
                    input=str(document.resolve()),
                    target=json.dumps(entries),
                    metadata={
                        "filename": document.name,
                        "reference_file": str(reference_path.resolve()),
                        "abbr": abbr,
                    },
                )
            )
    return samples
