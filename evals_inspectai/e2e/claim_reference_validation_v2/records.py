"""Claim Reference Validation records: an issue inventory plus the sources uploaded with it.

The workflow checks each citation against the supporting files uploaded with
the document, so a record carries them beside the inventory. They are split
off before the rest is read as an ``InventoryRecord``, so everything the
inventory loader checks (anchors present and on one line, ids unique) applies
unchanged, and they travel in the sample's metadata for the solver to upload
and the evidence check to read.
"""

from pathlib import Path

import yaml
from inspect_ai.dataset import MemoryDataset
from pydantic import BaseModel, ConfigDict, Field

from evals_inspectai.common.issue_inventory import (
    InventoryRecord,
    ResolvedInventory,
    inventory_to_sample,
    resolve_record,
)
from evals_inspectai.common.loaders import resolve_input

SOURCES_KEY = "sources"


class Source(BaseModel):
    """A supporting file uploaded with the document, as a user would attach a cited work."""

    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(description="Upload name; the app matches it, with its title, to a bibliography entry")
    markdown: str = Field(description="The file's text: inline markdown, or file://<path> relative to evals_inspectai/")


class ClaimRecord(BaseModel):
    """One document with its inventory and the sources its citations point to."""

    inventory: ResolvedInventory
    sources: list[Source]


def load_claim_records(path: Path) -> list[ClaimRecord]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a YAML list of records")
    records = []
    for entry in raw:
        sources = [Source.model_validate(s) for s in entry.get(SOURCES_KEY) or []]
        inventory = resolve_record(InventoryRecord.model_validate({k: v for k, v in entry.items() if k != SOURCES_KEY}))
        resolved = [s.model_copy(update={"markdown": resolve_input(s.markdown)}) for s in sources]
        records.append(ClaimRecord(inventory=inventory, sources=resolved))
    # Every level any record names is a titled kind, as ``load_inventory_records`` records it.
    named = sorted({e.title for r in records for e in r.inventory.expected_issues if e.title})
    return [r.model_copy(update={"inventory": r.inventory.model_copy(update={"named_titles": named})}) for r in records]


def claim_dataset(records: list[ClaimRecord], path: Path) -> MemoryDataset:
    samples = []
    for record in records:
        sample = inventory_to_sample(record.inventory)
        sample.metadata = {**(sample.metadata or {}), SOURCES_KEY: [s.model_dump() for s in record.sources]}
        samples.append(sample)
    return MemoryDataset(samples=samples, name=path.parent.name, location=str(path))
