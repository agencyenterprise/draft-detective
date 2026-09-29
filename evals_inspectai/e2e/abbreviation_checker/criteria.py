"""What Abbreviation Scan is judged on, beyond the generic issue checks.

The workflow has two outputs, scored separately because they fail separately.
Extraction agents, one per chunk of the document, record an occurrence
catalogue (``skills/abbreviation-extraction/SKILL.md``). Code then turns that
catalogue into the issues a user sees (``build_issues``, following
``skills/abbreviation-scan/SKILL.md``). The issues are scored with the generic
inventory checks. This module scores the catalogue, which is the part a model
produces.

Each expected occurrence is matched to at most one reported occurrence: first
by where it is (abbreviation, line, order on the line), then by abbreviation
and occurrence number (see ``_pair``). Recall and precision count occurrences
found and invented; exempt occurrences are not catalogued at all, so recording
one counts as invented. Over the matched occurrences, each field the rules read is
checked on its own: the inline definition (case and whitespace ignored), the
line span and the Abbreviations-section definition. So a
wrong line costs only ``lines_correct``, a missing definition costs only
``inline_definition_correct``, and a missed use costs recall once rather than
also costing every later use of that abbreviation, whose number it shifts.
The occurrence number itself is not checked separately. The workflow computes
it from the recorded uses, so it is wrong only when a use was missed or
invented, and recall and precision already count that.
"""

import math
import re
from typing import Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals_inspectai.common.issue_checks import fraction


class ExpectedOccurrence(BaseModel):
    """One occurrence a correct extraction records. Same fields as the workflow's ``AbbreviationItem``, minus its
    legacy exclusion flag and reason: exempt occurrences are not catalogued."""

    model_config = ConfigDict(extra="forbid")

    abbr: str = Field(min_length=1, description="The abbreviation in its singular base form, as the skill records it")
    occurrence_number: int = Field(ge=1, description="1 for the first appearance in the document, 2 for the second, ...")
    line_start: int = Field(ge=1)
    line_end: Optional[int] = Field(default=None, description="Defaults to line_start for a single-line occurrence")
    inline_definition: str = Field(default="", description="The 'Full Name (ABBR)' definition at this occurrence; empty when none")
    abbreviations_section_definition: Optional[str] = Field(
        default=None, description="The entry in the Abbreviations section; None when not listed or there is no section"
    )

    @model_validator(mode="after")
    def _single_line_by_default(self) -> "ExpectedOccurrence":
        if self.line_end is None:
            self.line_end = self.line_start
        if self.line_end < self.line_start:
            raise ValueError(f"{self.abbr}#{self.occurrence_number}: line_end precedes line_start")
        return self


class ExpectedCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    abbreviations_section_found: bool
    abbreviations: list[ExpectedOccurrence]

    @model_validator(mode="after")
    def _numbered_in_document_order(self) -> "ExpectedCatalogue":
        # Occurrence numbers run 1..n per abbreviation, in line order, as the workflow assigns them.
        by_abbr: dict[str, list[ExpectedOccurrence]] = {}
        for occurrence in self.abbreviations:
            by_abbr.setdefault(occurrence.abbr, []).append(occurrence)
        for abbr, occurrences in by_abbr.items():
            numbers = [o.occurrence_number for o in sorted(occurrences, key=lambda o: (o.line_start, o.occurrence_number))]
            if numbers != list(range(1, len(numbers) + 1)):
                raise ValueError(f"{abbr}: occurrence numbers {numbers} do not run 1..n in line order")
        return self


class ReportedOccurrence(BaseModel):
    """Local mirror of ``AbbreviationItem`` in the workflow state."""

    abbr: str
    inline_definition: str = ""
    occurrence_number: int = 0
    line_start: int = 0
    line_end: int = 0
    abbreviations_section_definition: Optional[str] = None


class ReportedCatalogue(BaseModel):
    """The catalogue fields of the workflow state the API returns. Other fields are ignored."""

    abbreviations: list[ReportedOccurrence] = Field(default_factory=list)
    abbreviations_section_found: bool = False


CATALOGUE_DESCRIPTIONS: dict[str, str] = {
    "occurrence_recall": "Share of expected occurrences the catalogue records, matched on (abbreviation, line, order on the line), else on (abbreviation, occurrence number). NaN on a document with no abbreviations.",
    "occurrence_precision": "Share of recorded occurrences that match an expected one. NaN on a document with no abbreviations, or when nothing was recorded.",
    "inline_definition_correct": "Of the matched occurrences, share whose inline definition (empty when none) matches the expected one, ignoring case and whitespace.",
    "lines_correct": "Of the matched occurrences, share whose line span equals the expected one.",
    "section_definition_correct": "Of the matched occurrences, share whose Abbreviations-section definition (none when not listed) matches, ignoring case and whitespace.",
    "section_found_correct": "1 if abbreviations_section_found matches the expected value, 0 otherwise.",
    "clean_catalogue": "On a document with no abbreviations: 1 if the catalogue is empty, 0 otherwise. NaN elsewhere.",
}
CATALOGUE_KEYS: tuple[str, ...] = tuple(CATALOGUE_DESCRIPTIONS)

CATALOGUE_LABELS: dict[str, str] = {
    "occurrence_recall": "Occ recall",
    "occurrence_precision": "Occ precision",
    "inline_definition_correct": "Inline def",
    "lines_correct": "Occ lines",
    "section_definition_correct": "Section def",
    "section_found_correct": "Section found",
    "clean_catalogue": "Clean catalogue",
}

# Explanations name at most this many occurrences per kind of miss, so a badly broken run stays readable.
_SHOWN = 6


def _text(value: Optional[str]) -> Optional[str]:
    """A definition compared without case or spacing, with an empty one the same as none."""
    if value is None:
        return None
    folded = re.sub(r"\s+", " ", value).strip().casefold()
    return folded or None


Occurrence = ExpectedOccurrence | ReportedOccurrence


def _label(occurrence: Occurrence) -> str:
    return f"{occurrence.abbr}#{occurrence.occurrence_number}"


def _by_location(occurrences: Sequence[Occurrence]) -> dict[tuple[str, int, int], int]:
    """Index of each occurrence by (abbreviation, line, order among that abbreviation's uses on the line)."""
    order = sorted(range(len(occurrences)), key=lambda i: (occurrences[i].line_start, occurrences[i].occurrence_number))
    keys: dict[tuple[str, int, int], int] = {}
    for i in order:
        abbr, line = occurrences[i].abbr.strip(), occurrences[i].line_start
        rank = sum(1 for key in keys if key[:2] == (abbr, line))
        keys[(abbr, line, rank)] = i
    return keys


def _by_number(occurrences: Sequence[Occurrence], left: set[int]) -> dict[tuple[str, int], int]:
    """Index of each still-unmatched occurrence by (abbreviation, occurrence number); a repeat keeps the first."""
    keys: dict[tuple[str, int], int] = {}
    for i in sorted(left):
        keys.setdefault((occurrences[i].abbr.strip(), occurrences[i].occurrence_number), i)
    return keys


def _pair(
    expected: Sequence[ExpectedOccurrence], reported: Sequence[ReportedOccurrence]
) -> tuple[list[tuple[ExpectedOccurrence, ReportedOccurrence]], list[ExpectedOccurrence], list[ReportedOccurrence]]:
    """One-to-one pairs, then the unmatched on each side.

    First on location (abbreviation, line, order on the line), then the rest on (abbreviation, occurrence number).
    Location comes first because the workflow numbers occurrences from the recorded ones: one missed use shifts
    every later number of that abbreviation, and pairing on numbers alone would then charge each later,
    correctly recorded use with a wrong line and flag. The fallback pairs a use recorded on the wrong line with
    the one it stands for, so that miss costs ``lines_correct`` rather than recall and precision."""
    matches: dict[int, int] = {}
    reported_at = _by_location(reported)
    for place, e in _by_location(expected).items():
        if place in reported_at:
            matches[e] = reported_at[place]
    left_e = set(range(len(expected))) - set(matches)
    left_r = set(range(len(reported))) - set(matches.values())
    reported_numbered = _by_number(reported, left_r)
    for number, e in _by_number(expected, left_e).items():
        if number in reported_numbered:
            matches[e] = reported_numbered[number]
    pairs = [(expected[e], reported[r]) for e, r in sorted(matches.items())]
    missing = [o for i, o in enumerate(expected) if i not in matches]
    paired = set(matches.values())
    invented = [o for i, o in enumerate(reported) if i not in paired]
    return pairs, missing, invented


def _field_checks(pairs: Sequence[tuple[ExpectedOccurrence, ReportedOccurrence]]) -> tuple[dict[str, float], list[str]]:
    checks: dict[str, list[tuple[bool, str]]] = {
        "inline_definition_correct": [
            (_text(e.inline_definition) == _text(r.inline_definition), f"{_label(e)} inline {r.inline_definition!r}, expected {e.inline_definition!r}")
            for e, r in pairs
        ],
        "lines_correct": [
            ((e.line_start, e.line_end) == (r.line_start, r.line_end), f"{_label(e)} lines {r.line_start}-{r.line_end}, expected {e.line_start}-{e.line_end}")
            for e, r in pairs
        ],
        "section_definition_correct": [
            (
                _text(e.abbreviations_section_definition) == _text(r.abbreviations_section_definition),
                f"{_label(e)} section {r.abbreviations_section_definition!r}, expected {e.abbreviations_section_definition!r}",
            )
            for e, r in pairs
        ],
    }
    values = {key: fraction([float(ok) for ok, _ in results]) for key, results in checks.items()}
    notes = []
    for key, results in checks.items():
        wrong = [note for ok, note in results if not ok]
        if wrong:
            notes.append(f"{key}: " + "; ".join(wrong[:_SHOWN]) + (f" (+{len(wrong) - _SHOWN} more)" if len(wrong) > _SHOWN else ""))
    return values, notes


def _listed(kind: str, occurrences: Sequence[Occurrence]) -> str:
    shown = ", ".join(f"{_label(o)} (line {o.line_start})" for o in occurrences[:_SHOWN])
    return f"{kind} {len(occurrences)}: {shown}" + (" ..." if len(occurrences) > _SHOWN else "")


def catalogue_scores(reported: ReportedCatalogue, expected: ExpectedCatalogue) -> tuple[dict[str, float], str]:
    """The catalogue keys (``CATALOGUE_KEYS``) and an explanation naming what was missed, invented or wrong.
    A key is NaN when the sample gives it nothing to judge."""
    values: dict[str, float] = {key: math.nan for key in CATALOGUE_KEYS}
    values["section_found_correct"] = float(reported.abbreviations_section_found == expected.abbreviations_section_found)
    notes = [] if values["section_found_correct"] else [
        f"abbreviations_section_found={reported.abbreviations_section_found}, expected {expected.abbreviations_section_found}"
    ]
    if not expected.abbreviations:
        values["clean_catalogue"] = float(not reported.abbreviations)
        if reported.abbreviations:
            notes.append(_listed("recorded on a document with no abbreviations", reported.abbreviations))
        return values, " | ".join(notes) if notes else "no abbreviations, none recorded"

    pairs, missing, invented = _pair(expected.abbreviations, reported.abbreviations)
    values["occurrence_recall"] = len(pairs) / len(expected.abbreviations)
    values["occurrence_precision"] = len(pairs) / len(reported.abbreviations) if reported.abbreviations else math.nan
    field_values, field_notes = _field_checks(pairs)
    values.update(field_values)
    notes.append(f"matched {len(pairs)}/{len(expected.abbreviations)} expected, {len(reported.abbreviations)} recorded")
    if missing:
        notes.append(_listed("missing", missing))
    if invented:
        notes.append(_listed("invented", invented))
    return values, " | ".join(notes + field_notes)
