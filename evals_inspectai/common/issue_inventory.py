"""Issue inventories: ground truth for any workflow that reports issues.

A sample lists the issues a correct run reports (the same ``DocumentIssue``
the workflows emit: a title, a location, an optional proposed edit) and the
sentences it must leave alone, instead of counting issues by title. Nothing
here is tied to skill-declared workflows; any eval whose dataset follows this
shape can use the loader and the checks in ``issue_checks.py``. Each
expected issue is anchored by a verbatim quote from the document, so the
scorer can tell whether the run found *that* sentence, and may carry
expectations about the proposed edit. Decoys are sentences that look like issues but are not, each tagged
with the reason, so a false positive names the rule that misfired.

Record shape (YAML)::

    - input: file://e2e/active_voice/files/report.md   # or inline markdown
      expected_issues:
        - title: Passive Voice                       # title a correct run uses; omit for free-form titles
          anchor: "Studies were identified through"    # verbatim quote that locates the issue (see .anchor);
                                                       # omit for an issue about something absent
          id: studies_identified                       # optional label for score explanations
          edit_expected: true                          # true: an edit must be attached; false: none may be
          edit:                                        # phrases a correct edit carries / avoids
            must_include: ["identified studies"]
            must_not_include: ["The authors"]
      decoys:
        - anchor: "The scope is limited to"
          reason: stative                              # free-form; names the rule that would misfire
      target_answer: "..."                             # optional free-text expectation for a model-graded scorer

Nothing here knows what a check is about. What counts as an issue, what an
edit must do beyond keeping the text intact, and what a decoy reason means are
the workflow's business; its task module and scorers supply those (see
``evals_inspectai/e2e/active_voice/``).

``line`` is resolved from the anchor at load time; a record may set it
explicitly when the anchor repeats. An expected issue about something the
document lacks (a missing section, a missing caption rule) has no sentence to
quote: it omits the anchor, names a title instead, and is matched on the title
alone, wherever the reported issue sits.
"""

from pathlib import Path
from typing import Optional, Sequence

import yaml
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals_inspectai.common.loaders import resolve_input

class EditExpectation(BaseModel):
    """What a correct proposed edit for an expected issue must and must not contain."""

    model_config = ConfigDict(extra="forbid")

    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)


class ExpectedIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(
        default=None,
        description=(
            "The issue title a correct run uses, or a stable part of it. Matched after "
            "normalising case, quotes and whitespace as whole words contained in the reported "
            "title (so 'Passive Voice' matches 'Passive Voice: Section Summary', and 'partially "
            "supported' matches 'Recommendation partially supported: expand to all sites', while "
            "'supported' does not match 'unsupported'). Omit when the workflow's titles carry no "
            "stable part: any title then matches, detection rests on the anchor being quoted or "
            "its line bracketed, and title_correct is not scored for the issue."
        ),
    )
    anchor: Optional[str] = Field(
        default=None,
        description=(
            "Verbatim text from the document that locates the issue, unique in the "
            "document unless `line` is set. It resolves the line the issue is on, and "
            "the issue counts as detected when a reported issue quotes it (in its "
            "description, long description, suggested action or an edit's original text) "
            "or brackets its line. Omit for an issue about something the document lacks: "
            "the issue then needs a title, has no line, and counts as detected when a "
            "reported issue carries that title, wherever it sits."
        ),
    )
    id: Optional[str] = Field(
        default=None,
        description=(
            "Short label used in score explanations ('missing studies_identified', "
            "'rates_tracked: 1/2 replacements ...') and to tell expected issues apart. Defaults to "
            "the anchor (the title when there is none), so it must be set when the same anchor is "
            "used twice with explicit lines; the loader rejects a record whose resolved ids repeat."
        ),
    )
    line: Optional[int] = Field(default=None, description="1-indexed document line; resolved from the anchor when omitted")
    edit_expected: Optional[bool] = Field(
        default=None,
        description="True when a correct run attaches a proposed edit for this issue, False when it must not; None to not check",
    )
    severity: Optional[str] = Field(
        default=None,
        description="The severity a correct run gives the issue (low, medium, high); feeds severity_correct. None to not check",
    )
    edit: Optional[EditExpectation] = Field(
        default=None,
        description="Phrases the proposed edit's replacement must carry or avoid; feeds edit_expected_phrases",
    )
    required: bool = Field(
        default=True,
        description=(
            "True: a correct run reports this issue, so missing it costs recall. False: reporting it is "
            "acceptable but not expected, so it is left out of recall while a report of it still counts as "
            "correct for precision. Use for borderline sentences a reasonable run may or may not flag; a "
            "sentence that must not be reported is a decoy, not an optional expected issue."
        ),
    )

    @model_validator(mode="after")
    def _located_or_titled(self) -> "ExpectedIssue":
        if self.anchor is None and self.title is None:
            raise ValueError("an expected issue needs an anchor, a title, or both")
        if self.anchor is None and self.line is not None:
            raise ValueError("`line` locates an anchor; an expected issue without one cannot set it")
        return self


class Decoy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: str = Field(description="Verbatim text of a sentence that looks like an issue but is not; must appear in the document")
    reason: str = Field(description="Which rule of the check would misfire here; becomes the metric no_fp_<reason>")
    title: Optional[str] = Field(
        default=None,
        description=(
            "The issue kind the sentence must not be reported under, matched like an expected issue's title. "
            "Set it when a correct run does report the sentence under another kind (every recommendation gets a "
            "support issue, but this one must not get 'Recommendation Not Actionable'): the decoy is then flagged "
            "only by an issue with this title that quotes the anchor or brackets its line. Omit it and any issue "
            "quoting the anchor flags it."
        ),
    )


class InventoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str = Field(description="The document: inline markdown, or file://<path> relative to evals_inspectai/")
    expected_issues: list[ExpectedIssue] = Field(
        default_factory=list, description="Issues a correct run reports; empty for a clean document"
    )
    decoys: list[Decoy] = Field(default_factory=list, description="Sentences a correct run leaves alone")
    notes: Optional[str] = Field(default=None, description="Why the record exists or how it was labelled; not scored")
    target_answer: Optional[str] = Field(
        default=None,
        description="Free-text expectation for a model-graded scorer, passed as the sample's target; the checks here ignore it",
    )


class ResolvedIssue(ExpectedIssue):
    # `line` stays optional: an expected issue without an anchor has none.
    id: str  # type: ignore[assignment]  # defaulted from the anchor or title, so no longer optional


class AnchoredIssue(ResolvedIssue):
    """A resolved expected issue that has an anchor, so its line is known."""

    anchor: str  # type: ignore[assignment]  # present, so no longer optional
    line: int  # type: ignore[assignment]  # resolved from the anchor, so no longer optional


def anchored(expected: ResolvedIssue) -> AnchoredIssue:
    """``expected`` typed as having an anchor and a line, for a check that only makes
    sense on a located issue; raises for an issue about something the document lacks."""
    if expected.anchor is None or expected.line is None:
        raise ValueError(f"expected issue {expected.id!r} has no anchor, so it has no line to check")
    return AnchoredIssue(**expected.model_dump())


class ResolvedInventory(BaseModel):
    """A record with every anchor located in the document text."""

    document: str
    expected_issues: list[ResolvedIssue]
    decoys: list[Decoy]
    notes: Optional[str] = None
    # Every title the dataset's expected issues name, across all records: the issue
    # kinds with fixed titles. Set by ``load_inventory_records``; the pairing uses it
    # so an untitled expected issue prefers a free-form report over one of these kinds.
    named_titles: list[str] = Field(default_factory=list)
    target_answer: Optional[str] = None


def normalize(text: str) -> str:
    """Lowercase, straight quotes, single spaces: how anchors are compared."""
    table = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})
    return " ".join(text.translate(table).lower().split())


def overlaps(a: str, b: str, words: int = 4) -> bool:
    """Whether two spans of text refer to the same sentence.

    True when one contains the other, or when they share a run of ``words``
    consecutive words. Used to pair an edit's quoted text with an expected issue's
    anchor, since a paragraph-level issue can carry edits for several
    sentences on the same line.
    """
    na, nb = normalize(a), normalize(b)
    if na in nb or nb in na:
        return True
    ta, tb = na.split(), nb.split()
    grams = {tuple(ta[i : i + words]) for i in range(len(ta) - words + 1)}
    return any(tuple(tb[i : i + words]) in grams for i in range(len(tb) - words + 1))


def locate_anchor(lines: list[str], anchor: str, label: str) -> int:
    """The 1-indexed line containing ``anchor`` exactly once across the document."""
    target = normalize(anchor)
    hits = [i for i, line in enumerate(lines, 1) if target in normalize(line)]
    if len(hits) != 1:
        state = "not found" if not hits else f"found on lines {hits}"
        raise ValueError(
            f"{label}: anchor {anchor!r} must occur on exactly one line of the document; {state}"
        )
    return hits[0]


def _resolve_line(lines: list[str], expected: ExpectedIssue, label: str) -> Optional[int]:
    """The line an expected issue's anchor sits on, or None when it has no anchor."""
    if expected.anchor is None:
        return None
    line = expected.line or locate_anchor(lines, expected.anchor, f"expected issue {label!r}")
    if normalize(expected.anchor) not in normalize(lines[line - 1]):
        raise ValueError(f"expected issue {label!r}: anchor is not on line {line}")
    return line


def resolve_record(record: InventoryRecord) -> ResolvedInventory:
    document = resolve_input(record.input)
    lines = document.split("\n")
    issues = []
    for expected in record.expected_issues:
        label = expected.id or expected.anchor or expected.title
        assert label is not None  # the model requires an anchor or a title
        line = _resolve_line(lines, expected, label)
        issues.append(ResolvedIssue(**{**expected.model_dump(), "line": line, "id": label}))
    repeated = sorted({i.id for i in issues if sum(1 for j in issues if j.id == i.id) > 1})
    if repeated:
        raise ValueError(
            f"expected issue ids must be unique within a record; repeated: {repeated}. "
            "Set `id` on expected issues that share an anchor."
        )
    for decoy in record.decoys:
        if not any(normalize(decoy.anchor) in normalize(line) for line in lines):
            raise ValueError(f"decoy {decoy.anchor!r} is not in the document")
    return ResolvedInventory(
        document=document,
        expected_issues=issues,
        decoys=record.decoys,
        notes=record.notes,
        target_answer=record.target_answer,
    )


def _read_records(path: Path) -> list[dict]:
    records = yaml.safe_load(path.read_text())
    if not isinstance(records, list):
        raise ValueError(f"{path}: expected a YAML list of records")
    return records


def load_inventory_records(path: Path) -> list[ResolvedInventory]:
    records = [resolve_record(InventoryRecord.model_validate(r)) for r in _read_records(path)]
    named = sorted({e.title for r in records for e in r.expected_issues if e.title})
    return [r.model_copy(update={"named_titles": named}) for r in records]


def decoy_reasons(records: Sequence[ResolvedInventory]) -> tuple[str, ...]:
    """Every decoy reason a dataset uses, sorted, so the scorer can declare one metric each."""
    return tuple(sorted({d.reason for r in records for d in r.decoys}))


def expects_titles(records: Sequence[ResolvedInventory]) -> bool:
    """Whether any expected issue in the dataset names a title: if none does, the
    workflow's titles are free-form and ``title_correct`` has nothing to score."""
    return any(e.title is not None for r in records for e in r.expected_issues)


def expects_anchors(records: Sequence[ResolvedInventory]) -> bool:
    """Whether any expected issue in the dataset has an anchor: if none does, every
    issue is about something the document lacks and ``anchor_in_range`` has nothing
    to score."""
    return any(e.anchor is not None for r in records for e in r.expected_issues)


def expects_severities(records: Sequence[ResolvedInventory]) -> bool:
    """Whether any expected issue in the dataset declares a severity: if none does,
    ``severity_correct`` has nothing to score."""
    return any(e.severity is not None for r in records for e in r.expected_issues)


def expects_edits(records: Sequence[ResolvedInventory]) -> bool:
    """Whether any expected issue in the dataset says something about proposed
    edits (``edit_expected`` or ``edit``): the workflow proposes edits and the
    edit-hygiene checks apply. A dataset that never mentions edits is for a
    workflow that reports issues only."""
    return any(e.edit_expected is not None or e.edit is not None for r in records for e in r.expected_issues)


def inventory_to_sample(inventory: ResolvedInventory) -> Sample:
    """A resolved inventory becomes a Sample whose input is the document, whose
    target is the record's free-text expectation (empty when it has none), and
    whose metadata carries the inventory for the scorers."""
    return Sample(
        input=inventory.document,
        target=inventory.target_answer or "",
        metadata={"inventory": inventory.model_dump()},
    )


def inventory_dataset(records: Sequence[ResolvedInventory], path: Path) -> MemoryDataset:
    """A dataset over already-loaded records, so a task that also needs the
    records (for decoy reasons, say) reads the file once."""
    return MemoryDataset(
        samples=[inventory_to_sample(r) for r in records], name=path.parent.name, location=str(path)
    )


def load_inventory_dataset(path: Path) -> MemoryDataset:
    """The dataset for an inventory file."""
    return inventory_dataset(load_inventory_records(path), path)
