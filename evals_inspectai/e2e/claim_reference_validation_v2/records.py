"""Claim Reference Validation records: an issue inventory plus the sources uploaded with it.

The workflow checks each citation against the supporting files uploaded with
the document, so a record carries them beside the inventory. They are loaded
as the suite's extra field, so everything the inventory loader checks
(anchors present and on one line, ids unique) applies unchanged, and they
travel in the sample's metadata for the solver to upload and the evidence
check to read.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evals_inspectai.common.inventory_suite import InventorySuite
from evals_inspectai.common.issue_inventory import ResolvedInventory
from evals_inspectai.common.loaders import resolve_input

SOURCES_KEY = "sources"
# The state field the solver adds, holding the citation records as issues.
CITATIONS_KEY = "citation_result"
RESULTS = (CITATIONS_KEY,)


class Source(BaseModel):
    """A supporting file uploaded with the document, as a user would attach a cited work."""

    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(description="Upload name; the app matches it, with its title, to a bibliography entry")
    markdown: str = Field(description="The file's text: inline markdown, or file://<path> relative to evals_inspectai/")


class ClaimRecord(BaseModel):
    """One document with its inventory and the sources its citations point to."""

    inventory: ResolvedInventory
    sources: list[Source]


def load_claim_suite(path: Path) -> InventorySuite:
    """One record per citation, so matching is one-to-one; a level is the verdict on a
    citation, not the kind of issue, so reports pair on the cited claim alone."""
    return InventorySuite.load(
        path, pairing="one_to_one", pair_on_location=True, extra_fields=(SOURCES_KEY,), results=RESULTS
    )


def sources_of(extra: dict[str, Any]) -> list[Source]:
    """A record's sources, their markdown read in."""
    sources = [Source.model_validate(s) for s in extra.get(SOURCES_KEY) or []]
    return [s.model_copy(update={"markdown": resolve_input(s.markdown)}) for s in sources]


def sources_metadata(extra: dict[str, Any]) -> dict[str, Any]:
    return {SOURCES_KEY: [s.model_dump() for s in sources_of(extra)]}


def load_claim_records(path: Path) -> list[ClaimRecord]:
    suite = load_claim_suite(path)
    return [ClaimRecord(inventory=r, sources=sources_of(x)) for r, x in zip(suite.records, suite.extras)]
