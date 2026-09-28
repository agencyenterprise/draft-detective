"""The dataset's record shape, and the loader-time check that its labels are the documents' text."""

from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict, Field

from evals_inspectai.common.loaders import resolve_input, yaml_dataset
from evals_inspectai.e2e.reference_text_extractor.matching import DocumentText


class ReferenceRecord(BaseModel):
    """One document and the entries of its reference section."""

    model_config = ConfigDict(extra="forbid")

    input: str = Field(description="The document as markdown, or file://<path> under evals_inspectai/")
    target_references: list[str] = Field(description="The reference entries a correct run extracts, in order")
    optional_references: list[str] = Field(
        default_factory=list, description="Entries the skill neither asks for nor rules out"
    )
    notes: str = Field(description="What the record tests")


def not_in_document(references: list[str], document: str) -> list[str]:
    """The references whose text does not appear in the document after normalization."""
    text = DocumentText(document.split("\n"))
    return [r for r in references if not text.contains(r)]


def record_to_sample(raw: dict) -> Sample:
    """A sample from one record, refusing any label that is not the document's own text."""
    record = ReferenceRecord.model_validate(raw)
    document = resolve_input(record.input)
    absent = not_in_document(record.target_references + record.optional_references, document)
    if absent:
        raise ValueError(f"expected references not found in {record.input[:60]!r}: {absent[:3]}")
    return Sample(
        input=document,
        metadata={
            "target_references": record.target_references,
            "optional_references": record.optional_references,
            "notes": record.notes,
        },
    )


def reference_dataset(path: Path) -> MemoryDataset:
    return yaml_dataset(path, record_to_sample)
