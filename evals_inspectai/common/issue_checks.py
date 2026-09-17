"""Deterministic checks of reported issues against an issue inventory: no
model calls, no knowledge of what the workflow is about, so any workflow that
emits issues can use them.

Three score functions, and the scorers built on them, kept separate so their
metrics are read apart: ``issue_detection_scores`` / ``issue_checks`` (the same
key set for every workflow), ``decoy_scores`` / ``decoy_checks`` (keys depend on
the dataset's decoy reasons), and ``extra_edit_scores`` (keys depend on the
workflow's own edit checks; the workflow wraps it with ``deterministic_scorer``
under a name of its own).

1. **Detection.** Each expected issue is *hit* when a reported issue with its
   title quotes its anchor, or brackets its line. Several expected issues may hit the
   same issue (a check that reports one issue per paragraph). From the hits:
   recall over required expected issues, precision over reported issues, and F0.5,
   which weights precision twice as much as recall, following the convention
   for grammatical-error detection, where a wrong correction costs the reader
   more than a missed one. Decoys a run quotes or edits are false positives
   broken down by reason.

2. **Edit hygiene.** For each hit expected: an edit is present or absent as the
   inventory expects; the edit's quote exists verbatim on the expected's line;
   the replacement carries the expected phrases and none of the forbidden
   ones; numbers, footnote markers and citations survive; no punctuation is
   stranded. A workflow adds its own per-edit checks (say, that the passive
   is gone) through ``EditCheck`` callables.

A metric is ``NaN`` when the sample gives it nothing to judge: Inspect leaves
a NaN key out of that metric's mean and counts the sample as unscored for it.
"""

import math
import re
from typing import Callable, Mapping, Optional, Sequence

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from evals_inspectai.common.simple_deep_agent_types import IssueItem, ProposedEdit, SimpleDeepAgentOutput
from evals_inspectai.common.issue_inventory import (
    Decoy,
    ResolvedIssue,
    ResolvedInventory,
    normalize,
    overlaps,
)

# A workflow-specific per-edit check: (edit) -> pass?  Reported as edit_<name>.
# A workflow's own per-edit verdict: True or False, or None when the check has
# nothing to assess on that edit, which leaves it out of the fraction.
EditCheck = Callable[[ProposedEdit], Optional[bool]]

DETECTION_KEYS: tuple[str, ...] = (
    "recall",
    "precision",
    "f0_5",
    "clean_document_untouched",
    "title_correct",
    "severity_correct",
    "anchor_in_range",
)
EDIT_KEYS: tuple[str, ...] = (
    "edit_present_when_expected",
    "edit_absent_when_not_expected",
    "edit_quote_on_line",
    "edit_expected_phrases",
    "edit_keeps_numbers_and_markers",
    "edit_punctuation",
)

# Inspect's unscored sentinel: `Score.unscored()` sets a NaN value, and the
# metric expansion for dict-valued scores skips NaN keys (counted as unscored)
# instead of letting them pull the mean down. See the Inspect scoring policy
# (inspect.aisi.org.uk/scoring-policy.html). Used per key here, since one
# check on a sample can have nothing to judge while the others do.
NOT_APPLICABLE = math.nan

# One line per metric, for the eval's Task metadata so the log viewer's Info tab
# says what each column checks. A value of NaN means the sample gave the check
# nothing to judge, and Inspect leaves it out of the mean.
DETECTION_DESCRIPTIONS: dict[str, str] = {
    "recall": "Share of required expected issues covered by a reported issue (same title and the anchor quoted or its line bracketed).",
    "precision": "Share of reported issues that cover at least one expected issue.",
    "f0_5": "F-beta with beta 0.5: precision weighted twice as much as recall, as in grammatical-error detection.",
    "clean_document_untouched": "On a sample with no expected issues: 1 if nothing was reported, 0 otherwise.",
    "title_correct": "Of the covered expected issues, share reported under the expected title.",
    "severity_correct": "Of the covered expected issues that declare a severity, share reported with it.",
    "anchor_in_range": "Of the covered expected issues, share whose anchor line lies inside the reported line range.",
}
EDIT_DESCRIPTIONS: dict[str, str] = {
    "edit_present_when_expected": "For expected issues marked edit_expected: true, share that got at least one proposed edit.",
    "edit_absent_when_not_expected": "For expected issues marked edit_expected: false, share that got no proposed edit.",
    "edit_quote_on_line": "Share of edits whose original_text occurs verbatim on the expected issue's line.",
    "edit_expected_phrases": "Share of edits whose replacement carries every must_include phrase and no must_not_include phrase.",
    "edit_keeps_numbers_and_markers": "Share of edits whose replacement keeps every number, footnote marker and citation of the original.",
    "edit_punctuation": "Share of edits whose replacement adds no stranded punctuation (',.', ' .', doubled spaces) the original lacked.",
}


def decoy_descriptions(reasons: Sequence[str]) -> dict[str, str]:
    return {
        f"no_fp_{reason}": f"1 if no decoy tagged '{reason}' was quoted or edited by a reported issue in the sample, 0 if one was; NaN when the sample has no such decoy."
        for reason in reasons
    }

# A number ends in a digit (or %), so a sentence-final "Figure 1." yields "1", not "1.".
_NUMBER_RE = re.compile(r"\d(?:[\d,.–\-]*\d)?%?")
_FOOTNOTE_RE = re.compile(r"\[\[\d+\]\]\(#footnote-\d+\)")
_CITATION_RE = re.compile(r"\([A-Z][^()]*?\d{4}[a-z]?(?:,\s*p\.\s*\d+)?\)")
_STRANDED_RE = re.compile(r",\s*[.;,]|\s[.,;]|\.\.(?!\.)|\s{2,}")


def _issue_text(issue: IssueItem) -> str:
    parts = [issue.title, issue.description, issue.long_description or "", issue.suggested_action or ""]
    parts += [edit.original_text for edit in issue.edits]
    return normalize(" ".join(parts))


def _title_matches(issue: IssueItem, kind: str) -> bool:
    title = normalize(issue.title)
    return title == normalize(kind) or title.startswith(normalize(kind) + ":")


def hit_issue(expected: ResolvedIssue, issues: Sequence[IssueItem]) -> Optional[int]:
    """Index of the issue that reports this expected, or None.

    A title match plus the anchor quoted is the strongest evidence; then a title
    match bracketing the line; then the anchor quoted under another title. The
    last still counts as detected so the title metric, not recall, records the
    mislabel.
    """
    anchor = normalize(expected.anchor)
    tiers: list[list[int]] = [[], [], []]
    for index, issue in enumerate(issues):
        same_title = _title_matches(issue, expected.title)
        quoted = anchor in _issue_text(issue)
        in_range = issue.start_line <= expected.line <= issue.end_line
        if same_title and quoted:
            tiers[0].append(index)
        elif same_title and in_range:
            tiers[1].append(index)
        elif quoted:
            tiers[2].append(index)
    for tier in tiers:
        if tier:
            return tier[0]
    return None


def decoy_hits(decoys: Sequence[Decoy], issues: Sequence[IssueItem]) -> list[Decoy]:
    texts = [_issue_text(issue) for issue in issues]
    return [d for d in decoys if any(normalize(d.anchor) in t for t in texts)]


def edits_for(expected: ResolvedIssue, issue: IssueItem) -> list[ProposedEdit]:
    """The issue's edits that quote this expected's sentence.

    Matched on text, never on line alone: a paragraph-level issue carries the
    edits for every sentence on that line, and each must be judged against
    its own expected.
    """
    return [e for e in issue.edits if overlaps(expected.anchor, e.original_text)]


def _fraction(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else NOT_APPLICABLE


def _tokens(text: str) -> list[str]:
    return sorted(_NUMBER_RE.findall(text) + _FOOTNOTE_RE.findall(text) + _CITATION_RE.findall(text))


def _stranded(text: str) -> set[str]:
    """Punctuation faults, read with footnote markers removed so ",[[9]](#footnote-10)." counts as ",."."""
    return set(_STRANDED_RE.findall(_FOOTNOTE_RE.sub("", text)))


def edit_checks(
    expected: ResolvedIssue,
    issue: IssueItem,
    lines: Sequence[str],
    extra: Optional[Mapping[str, EditCheck]] = None,
) -> dict[str, tuple[float, str]]:
    """The edit-layer verdicts for one hit expected, with the detail behind each.

    Only the checks that apply are present: presence or absence when the
    inventory says which, and the hygiene checks only when edits exist.
    """
    edits = edits_for(expected, issue)
    out: dict[str, tuple[float, str]] = {}
    if expected.edit_expected is True:
        out["edit_present_when_expected"] = (
            float(bool(edits)),
            f"{expected.id}: {'edit attached' if edits else 'no edit attached, although one is expected'}",
        )
    if expected.edit_expected is False:
        out["edit_absent_when_not_expected"] = (
            float(not edits),
            f"{expected.id}: {'no edit, as expected' if not edits else 'an edit is attached where none should be'}",
        )
    if not edits:
        return out

    line_text = lines[expected.line - 1] if 0 < expected.line <= len(lines) else ""
    on_line = [float(normalize(e.original_text) in normalize(line_text)) for e in edits]
    out["edit_quote_on_line"] = (_fraction(on_line), f"{expected.id}: {int(sum(on_line))}/{len(edits)} quotes found verbatim on line {expected.line}")

    if expected.edit is not None:
        ok = []
        for e in edits:
            repl = normalize(e.replacement_text)
            missing = [p for p in expected.edit.must_include if normalize(p) not in repl]
            forbidden = [p for p in expected.edit.must_not_include if normalize(p) in repl]
            ok.append(float(not missing and not forbidden))
        out["edit_expected_phrases"] = (_fraction(ok), f"{expected.id}: {int(sum(ok))}/{len(edits)} replacements carry the expected phrasing")

    kept = [float(_tokens(e.original_text) == _tokens(e.replacement_text)) for e in edits]
    out["edit_keeps_numbers_and_markers"] = (_fraction(kept), f"{expected.id}: {int(sum(kept))}/{len(edits)} replacements keep every number, footnote marker and citation")

    clean = [float(not (_stranded(e.replacement_text) - _stranded(e.original_text))) for e in edits]
    out["edit_punctuation"] = (_fraction(clean), f"{expected.id}: {int(sum(clean))}/{len(edits)} replacements add no stranded punctuation")

    for name, check in (extra or {}).items():
        verdicts = [check(e) for e in edits]
        results = [float(v) for v in verdicts if v is not None]
        if not results:
            continue  # nothing this check could assess here; the key stays NaN
        skipped = len(verdicts) - len(results)
        detail = f"{expected.id}: {int(sum(results))}/{len(results)} replacements pass {name}"
        out[f"edit_{name}"] = (_fraction(results), detail + (f" ({skipped} not assessable)" if skipped else ""))
    return out


def _hit_pairs(
    issues: Sequence[IssueItem], inventory: ResolvedInventory
) -> tuple[dict[str, Optional[int]], list[tuple[ResolvedIssue, IssueItem]]]:
    hits = {e.id: hit_issue(e, issues) for e in inventory.expected_issues}
    pairs = [(e, issues[i]) for e in inventory.expected_issues if (i := hits[e.id]) is not None]
    return hits, pairs


def issue_detection_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory
) -> tuple[dict[str, float], str]:
    """Detection and generic edit hygiene: the same key set for every workflow.

    Keys: ``DETECTION_KEYS`` and ``EDIT_KEYS``; NaN where not applicable.
    """
    lines = inventory.document.split("\n")
    expected_issues = inventory.expected_issues
    values: dict[str, float] = {key: NOT_APPLICABLE for key in DETECTION_KEYS + EDIT_KEYS}
    notes: list[str] = []

    hits, hit_pairs = _hit_pairs(issues, inventory)
    required = [e for e in expected_issues if e.required]
    found_required = [e for e in required if hits[e.id] is not None]
    hit_indices = {i for i in hits.values() if i is not None}

    if expected_issues:
        recall = len(found_required) / len(required) if required else 1.0
        precision = len(hit_indices) / len(issues) if issues else (1.0 if not required else 0.0)
        values["recall"] = recall
        values["precision"] = precision
        values["f0_5"] = 1.25 * precision * recall / (0.25 * precision + recall) if (precision + recall) else 0.0
        missing = [e.id for e in required if hits[e.id] is None]
        notes.append(f"recall {len(found_required)}/{len(required)}" + (f" (missing {', '.join(missing)})" if missing else ""))
        notes.append(f"precision {len(hit_indices)}/{len(issues)} issues matched an expected issue")
    else:
        values["clean_document_untouched"] = float(not issues)
        notes.append("clean document: " + ("nothing reported" if not issues else f"{len(issues)} issue(s) reported"))

    if hit_pairs:
        values["title_correct"] = _fraction([float(_title_matches(i, e.title)) for e, i in hit_pairs])
        values["severity_correct"] = _fraction([float(i.severity == e.severity) for e, i in hit_pairs if e.severity])
        values["anchor_in_range"] = _fraction([float(i.start_line <= e.line <= i.end_line) for e, i in hit_pairs])
        collected: dict[str, list[float]] = {}
        for e, i in hit_pairs:
            for key, (value, detail) in edit_checks(e, i, lines).items():
                collected.setdefault(key, []).append(value)
                if value < 1.0:
                    notes.append(detail)
        for key, vals in collected.items():
            values[key] = _fraction(vals)

    return values, " | ".join(notes) if notes else "all checks passed"


def extra_edit_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory, checks: Mapping[str, EditCheck]
) -> tuple[dict[str, float], str]:
    """A workflow's own per-edit checks, keyed ``edit_<name>``, over the edits of detected expected issues."""
    lines = inventory.document.split("\n")
    values: dict[str, float] = {f"edit_{name}": NOT_APPLICABLE for name in checks}
    notes: list[str] = []
    collected: dict[str, list[float]] = {}
    for e, i in _hit_pairs(issues, inventory)[1]:
        results = edit_checks(e, i, lines, checks)
        for name in checks:
            key = f"edit_{name}"
            if key in results:
                value, detail = results[key]
                collected.setdefault(key, []).append(value)
                if value < 1.0:
                    notes.append(detail)
    for key, vals in collected.items():
        values[key] = _fraction(vals)
    return values, " | ".join(notes) if notes else "all checks passed"


def decoy_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory, reasons: Sequence[str]
) -> tuple[dict[str, float], str]:
    """False positives by reason: ``no_fp_<reason>`` is 1 when no decoy of that
    reason was flagged, 0 when one was, NaN when the sample has no such decoy.

    ``reasons`` is the dataset-wide list, so every sample returns the same keys.
    """
    present = {d.reason for d in inventory.decoys}
    hit = decoy_hits(inventory.decoys, issues)
    values: dict[str, float] = {}
    notes: list[str] = []
    for reason in reasons:
        key = f"no_fp_{reason}"
        if reason not in present:
            values[key] = NOT_APPLICABLE
            continue
        anchors = [d.anchor for d in hit if d.reason == reason]
        values[key] = float(not anchors)
        if anchors:
            notes.append(f"false positive ({reason}): " + "; ".join(repr(a) for a in anchors))
    return values, " | ".join(notes) if notes else "no decoy flagged"


# --- Inspect scorers ------------------------------------------------------------
#
# Scores are dict-valued, one key per check. The "*" glob gives every key its
# own mean and standard error. A NaN value marks a sample as unscored for that key.
PER_KEY_METRICS = {"*": [mean(), stderr()]}

Scoring = Callable[[Sequence[IssueItem], ResolvedInventory], tuple[dict[str, float], str]]


def issues_from_state(state: TaskState) -> tuple[list[IssueItem], Optional[str]]:
    """The issues a workflow run reported, from the API state the solver captured."""
    try:
        output = SimpleDeepAgentOutput.model_validate_json(state.output.completion)
    except ValidationError as e:
        return [], f"could not parse the workflow state: {e}"
    return (output.result.issues if output.result else []), None


def inventory_from_state(state: TaskState) -> ResolvedInventory:
    return ResolvedInventory.model_validate(state.metadata["inventory"])


def deterministic_scorer(scoring: Scoring) -> Scorer:
    """Wrap a ``(issues, inventory) -> (values, explanation)`` function as a scorer.

    A run whose state cannot be parsed scores 0 on every key the function
    would have produced, with the parse error as the explanation.
    """

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state)
        values, explanation = scoring(issues, inventory_from_state(state))
        if error:
            return Score(value={key: 0.0 for key in values}, explanation=error)
        return Score(value=values, explanation=explanation)

    return score


@scorer(metrics=PER_KEY_METRICS)
def issue_checks() -> Scorer:
    """Reported issues against the expected ones: recall, precision, F0.5, titles,
    lines, edit presence and text integrity. The same keys for every issue-inventory eval."""
    return deterministic_scorer(issue_detection_scores)


@scorer(metrics=PER_KEY_METRICS)
def decoy_checks(reasons: Sequence[str]) -> Scorer:
    """False positives by decoy reason, ``no_fp_<reason>``.

    ``reasons`` is the dataset-wide list, so every sample's score carries the
    same keys, which Inspect requires of dict-valued scores.
    """
    return deterministic_scorer(lambda issues, inventory: decoy_scores(issues, inventory, reasons))
