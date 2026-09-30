"""Ground truth for the Reference Validation eval: one reference per record, labelled field by field.

The workflow reports, for each reference, a problem type for each of five fields
(author, title, publisher, year, identifier) and a final result derived from
them. A single label for the final result cannot tell a run that flagged the
wrong field from one that flagged the right one, so each record says what every
field should get, which phrases a correction must carry, and whether the
reference is fabricated. A list accepts any of its values, for a field the
skill leaves open or a fact the web disputes.
"""

import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FIELDS = ("author", "title", "publisher", "year", "identifier")
Problem = Literal["correct", "missing", "incorrect", "other"]
Result = Literal["correct", "missing_fields", "incorrect_fields"]

# What a fabricated reference's fields may be reported as: nothing can be verified.
_UNVERIFIABLE: list[Problem] = ["incorrect", "other"]
# A fabricated reference's identifier depends on what it cites. A DOI, arXiv ID, ISBN or ISSN
# is fabricated too, so it must not pass as correct. A plain URL is not an identifier under
# the skill, but a run may fairly report the dead link there. Nothing cited: the identifier is
# optional, so it is correct, or unverifiable.
_FABRICATED_IDENTIFIER: list[Problem] = ["incorrect", "other"]
_FABRICATED_URL: list[Problem] = ["correct", "incorrect", "other"]
_NO_IDENTIFIER: list[Problem] = ["correct", "other"]
_IDENTIFIER_RE = re.compile(r"\b10\.\d{4,9}/|arxiv[:.]|\bISBN\b|\bISSN\b", re.I)
_URL_RE = re.compile(r"https?://", re.I)
_CORRECT: tuple[Result, ...] = ("correct",)


def _as_list(value: object) -> object:
    return [value] if isinstance(value, str) else value


class ReferenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    reference: str = Field(description="The bibliographic entry, placed alone under a References heading")
    result: list[Result] = Field(default_factory=lambda: list(_CORRECT), description="Final results a correct run may give")
    fields: dict[str, list[Problem]] = Field(
        default_factory=dict, description="Accepted problem types per field; a field left out must be correct"
    )
    corrections: dict[str, str] = Field(
        default_factory=dict,
        description="Per field, a phrase the field's suggested value or the updated reference must carry",
    )
    not_found: bool = Field(default=False, description="A fabricated reference: nothing verifies, no updated reference")
    rationale: Optional[str] = Field(default=None, description="The labeller's account, for the judged criterion")
    notes: Optional[str] = None

    @field_validator("result", mode="before")
    @classmethod
    def _one_or_many_results(cls, value: object) -> object:
        return _as_list(value)

    @field_validator("fields", mode="before")
    @classmethod
    def _one_or_many_problems(cls, value: object) -> object:
        return {k: _as_list(v) for k, v in value.items()} if isinstance(value, dict) else value

    @model_validator(mode="after")
    def _known_fields(self) -> "ReferenceRecord":
        unknown = (set(self.fields) | set(self.corrections)) - set(FIELDS)
        if unknown:
            raise ValueError(f"{self.id}: unknown fields {sorted(unknown)}")
        if self.not_found and (self.fields or self.corrections or self.result not in (["correct"], ["incorrect_fields"])):
            raise ValueError(f"{self.id}: a not-found record sets no result, fields or corrections")
        if self.not_found:
            # Step 6: a reference that cannot be located is incorrect_fields. Stored, so the
            # record survives a round trip through sample metadata.
            self.result = ["incorrect_fields"]
        return self

    @property
    def is_bare_url(self) -> bool:
        """A reference that is only a URL, which the skill's Step 1 reconstructs in full."""
        return re.fullmatch(r"https?://\S+", self.reference.strip()) is not None

    def accepted(self, field: str) -> list[Problem]:
        """The problem types a correct run may give ``field``."""
        if self.not_found and field == "identifier":
            return self._fabricated_identifier()
        if self.not_found:
            return _UNVERIFIABLE
        return self.fields.get(field, ["correct"])

    def _fabricated_identifier(self) -> list[Problem]:
        if _IDENTIFIER_RE.search(self.reference):
            return _FABRICATED_IDENTIFIER
        return _FABRICATED_URL if _URL_RE.search(self.reference) else _NO_IDENTIFIER


def load_records(path: Path) -> list[ReferenceRecord]:
    records = [ReferenceRecord.model_validate(r) for r in yaml.safe_load(path.read_text())]
    ids = [r.id for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: record ids repeat")
    return records


def reference_dataset(records: list[ReferenceRecord], path: Path) -> MemoryDataset:
    """One sample per record: the reference alone under a References heading, as the
    workflow's reference extraction expects a document to present it."""
    return MemoryDataset(
        samples=[
            Sample(id=r.id, input=f"## References\n\n{r.reference}\n", metadata={"record": r.model_dump()})
            for r in records
        ],
        name=path.parent.name,
        location=str(path),
    )
