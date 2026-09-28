"""What Reference Extraction is judged on: the reference list it returns.

The workflow emits references, not issues, so the issue-inventory checks do
not apply. Each sample lists the entries of its document's reference section
as the skill defines them (entry numbers removed, repeated-author placeholders
resolved, wrapped lines merged). The extracted references are paired one to
one with those (``matching.match``): identical texts first, then tolerant
matches, so an entry with a spacing or punctuation difference, or one missing
its trailing URL, still counts as found while ``text_exact`` records that it is
not the entry as written. From the pairing: recall, precision, F1, and a clean
document left alone. Two checks read the document itself rather than the
labels: every extracted reference is text the document contains, and the
lines each one names contain it.

A sample may also list optional references: entries the skill neither asks for
nor rules out (a "See" cross-reference in a bibliography). Extracting one
costs no precision and missing one costs no recall.

A metric is ``NaN`` when the sample gives it nothing to judge: Inspect leaves
a NaN key out of that metric's mean.
"""

import math
from typing import Optional, Sequence

from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field, ValidationError

from evals_inspectai.common.issue_checks import PER_KEY_METRICS
from evals_inspectai.common.scorers import failed_score
from evals_inspectai.e2e.reference_text_extractor.matching import DocumentText, compact, match

NAN = math.nan
# How many missing or extra references an explanation names, and how much of each.
LISTED = 5
SNIPPET = 90


class ExtractedReference(BaseModel):
    """Local mirror of the workflow state's reference."""

    id: str = ""
    text: str = ""
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class ReferenceExtractionOutput(BaseModel):
    """Local mirror of the workflow state's outputs."""

    extracted_references: list[ExtractedReference] = Field(default_factory=list)
    reasoning: str = ""


DESCRIPTIONS = {
    "recall": "Share of the expected references paired with an extracted one (identical after normalization, or a tolerant match); NaN when none is expected.",
    "precision": "Share of the extracted references paired with an expected one, optional entries left out; NaN when nothing was extracted.",
    "f1": "Harmonic mean of recall and precision; 0 when nothing expected was found; NaN when none is expected.",
    "clean_document_untouched": "On a document with no reference entries, 1 when nothing was extracted, else 0; NaN otherwise.",
    "text_exact": "Of the paired references, share whose text is identical to the expected entry after normalization (entities, escapes, quotes and spacing); NaN when none was paired.",
    "verbatim_in_document": "Share of the extracted references whose text the document contains (list markers ignored, a resolved repeated-author placeholder allowed); catches invented or rewritten entries; NaN when nothing was extracted.",
    "lines_bracket_text": "Of the extracted references that are verbatim in the document and name their lines, share whose text lies within those lines; NaN when there are none.",
}
KEYS = tuple(DESCRIPTIONS)

SCORE_LABELS = {
    "recall": "Recall",
    "precision": "Precision",
    "f1": "F1",
    "clean_document_untouched": "Clean",
    "text_exact": "Exact text",
    "verbatim_in_document": "Verbatim",
    "lines_bracket_text": "Lines",
}


def _fraction(passed: int, total: int) -> float:
    return passed / total if total else NAN


def _listed(label: str, texts: Sequence[str]) -> list[str]:
    if not texts:
        return []
    shown = [t if len(t) <= SNIPPET else t[:SNIPPET] + "…" for t in texts[:LISTED]]
    more = f" (+{len(texts) - LISTED} more)" if len(texts) > LISTED else ""
    return [f"{label} {len(texts)}: {shown}{more}"]


def _in_lines(ref: ExtractedReference, document: DocumentText, line_count: int) -> Optional[bool]:
    """Whether the reference's text lies within its own line range; None when it names none.
    Read against the whole document, so a repeated-author placeholder in range still
    resolves to the previous entry's author outside it."""
    if ref.start_line is None or ref.end_line is None:
        return None
    if not 1 <= ref.start_line <= ref.end_line <= line_count:
        return False
    return document.contains(ref.text, ref.start_line, ref.end_line)


def reference_scores(
    extracted: Sequence[ExtractedReference],
    expected: Sequence[str],
    optional: Sequence[str],
    document: str,
) -> tuple[dict[str, float], str]:
    """Every key of ``DESCRIPTIONS`` for one run, and an explanation naming what was
    missed, what was extra, and what was not the document's text."""
    texts = [r.text for r in extracted]
    pairs = match(texts, expected)
    paired = {i for i, _ in pairs}
    unpaired = [i for i in range(len(texts)) if i not in paired]
    tolerated = {unpaired[k] for k, _ in match([texts[i] for i in unpaired], optional)}
    extra = [texts[i] for i in unpaired if i not in tolerated]
    found = {j for _, j in pairs}
    missing = [e for j, e in enumerate(expected) if j not in found]
    inexact = [texts[i] for i, j in pairs if compact(texts[i]) != compact(expected[j])]

    lines = document.split("\n")
    text = DocumentText(lines)
    in_document = [text.contains(r.text) for r in extracted]
    verbatim = [r for r, ok in zip(extracted, in_document) if ok]
    invented = [r.text for r, ok in zip(extracted, in_document) if not ok]
    placed = [(r, ok) for r in verbatim if (ok := _in_lines(r, text, len(lines))) is not None]
    misplaced = [f"{r.start_line}-{r.end_line}: {r.text}" for r, ok in placed if not ok]

    recall = _fraction(len(pairs), len(expected))
    precision = _fraction(len(pairs), len(pairs) + len(extra))
    values = {
        "recall": recall,
        "precision": precision,
        "f1": NAN if not expected else (2 * recall * precision / (recall + precision) if pairs else 0.0),
        "clean_document_untouched": NAN if expected else float(not extra),
        "text_exact": _fraction(len(pairs) - len(inexact), len(pairs)),
        "verbatim_in_document": _fraction(len(verbatim), len(extracted)),
        "lines_bracket_text": _fraction(sum(ok for _, ok in placed), len(placed)),
    }
    notes = [f"{len(pairs)}/{len(expected)} expected found, {len(extracted)} extracted ({len(tolerated)} optional)"]
    notes += _listed("missing", missing) + _listed("extra", extra) + _listed("inexact", inexact)
    notes += _listed("not verbatim", invented)
    notes += _listed("lines do not hold the text", misplaced)
    return values, " | ".join(notes)


@scorer(metrics=PER_KEY_METRICS)
def reference_checks() -> Scorer:
    """The extracted references against the sample's expected entries and its document."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = ReferenceExtractionOutput.model_validate_json(state.output.completion)
        except ValidationError as e:
            return failed_score(KEYS, f"could not parse the workflow state: {e}")
        values, explanation = reference_scores(
            output.extracted_references,
            state.metadata.get("target_references", []),
            state.metadata.get("optional_references", []),
            state.input_text,
        )
        return Score(value=values, explanation=explanation)

    return score
