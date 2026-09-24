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
   title quotes its anchor or brackets its line, or an issue under another title
   quotes its anchor (a mislabel, recorded by the title metric, not recall). Several expected issues may hit the
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

def issue_check_keys(edits: bool = True, titles: bool = True) -> tuple[str, ...]:
    """The keys ``issue_checks(edits=..., titles=...)`` emits, for viewer columns and
    descriptions: the detection keys, without ``title_correct`` when the inventory names
    no titles, plus the edit-hygiene keys when the workflow proposes edits."""
    detection = DETECTION_KEYS if titles else tuple(k for k in DETECTION_KEYS if k != "title_correct")
    return detection + EDIT_KEYS if edits else detection


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
    "recall": "Share of required expected issues covered by a reported issue (same title and the anchor quoted or its line bracketed, or the anchor quoted under another title).",
    "precision": "Share of reported issues that cover at least one expected issue.",
    "f0_5": "F-beta with beta 0.5: precision weighted twice as much as recall, as in grammatical-error detection.",
    "clean_document_untouched": "On a sample with no expected issues: 1 if nothing was reported, 0 otherwise.",
    "title_correct": "Of the covered expected issues that name a title, share reported under it. NaN when the inventory names none (free-form titles).",
    "severity_correct": "Of the covered expected issues that declare a severity, share reported with it.",
    "anchor_in_range": "Of the covered expected issues, share whose anchor line lies inside the reported line range.",
}
EDIT_DESCRIPTIONS: dict[str, str] = {
    "edit_present_when_expected": "For expected issues marked edit_expected: true, share that got at least one proposed edit.",
    "edit_absent_when_not_expected": "For expected issues marked edit_expected: false, share that got no proposed edit.",
    "edit_quote_on_line": "Share of edits whose original_text occurs verbatim on the expected issue's line.",
    "edit_expected_phrases": "Share of edits whose replacement, read within the sentence it produces on the line, carries every must_include phrase and no must_not_include phrase.",
    "edit_keeps_numbers_and_markers": "Share of edits whose replacement keeps every number (with its percentage unit, if any), footnote marker and citation of the original.",
    "edit_punctuation": "Share of edits whose replacement adds no stranded punctuation (',.', ' .', doubled spaces) the original lacked.",
}


def decoy_descriptions(reasons: Sequence[str]) -> dict[str, str]:
    return {
        f"no_fp_{reason}": f"1 if no decoy tagged '{reason}' was flagged in the sample (quoted or edited by a reported issue, or, for a decoy tied to a title, reported under that title), 0 if one was; NaN when the sample has no such decoy."
        for reason in reasons
    }

# A number ends in a digit, so a sentence-final "Figure 1." yields "1", not "1.". A
# percentage unit written as "%", "percent" or "per cent" is captured with it and
# canonicalised to "%", so "7%" and "7 percent" are the same token while "7" is not.
_NUMBER_RE = re.compile(r"(\d(?:[\d,.–\-]*\d)?)(\s*(?:%|percent\b|per cent\b))?", re.I)
_FOOTNOTE_RE = re.compile(r"\[\[\d+\]\]\(#footnote-\d+\)")
_CITATION_RE = re.compile(r"\([A-Z][^()]*?\d{4}[a-z]?(?:,\s*p\.\s*\d+)?\)")
_STRANDED_RE = re.compile(r",\s*[.;,]|\s[.,;]|\.\.(?!\.)|\s{2,}")


def _issue_text(issue: IssueItem) -> str:
    parts = [issue.title, issue.description, issue.long_description or "", issue.suggested_action or ""]
    parts += [edit.original_text for edit in issue.edits]
    return normalize(" ".join(parts))


def _title_matches(issue: IssueItem, kind: Optional[str]) -> bool:
    """The expected title appears in the reported one as whole words, after
    normalisation; an expected issue with no title matches any. Whole words so
    that "supported" does not match "unsupported"."""
    if kind is None:
        return True
    pattern = r"(?<!\w)" + re.escape(normalize(kind)) + r"(?!\w)"
    return re.search(pattern, normalize(issue.title)) is not None


# Added to the tier of an untitled expected issue reported under a title another
# expected issue of the inventory names: above every plain tier, below the cost of
# leaving it unmatched (see _UNMATCHED_OPTIONAL).
_CLAIMED_TITLE_PENALTY = 6


def hit_tier(expected: ResolvedIssue, issue: IssueItem, claimed: Sequence[str] = ()) -> Optional[int]:
    """How well ``issue`` reports ``expected``, lower is stronger; None when it
    does not report it.

    Three tiers of evidence: a title match with the anchor quoted, a title match
    bracketing the line, the anchor quoted under another title (still detected,
    so the title metric, not recall, records the mislabel). Within a tier, an
    issue whose line range brackets the expected line ranks above one whose
    range is elsewhere: when one issue quotes both a recommendation and its
    restatement, its range says which occurrence it reports, and without that
    the pairing would depend on report order.

    ``claimed`` are the titles the inventory names for other expected issues.
    An untitled expected issue (free-form titles) matches any title, but an
    issue under a claimed title is evidence for that other kind first: it
    still counts, ranked below every free-form report, so an extra issue of a
    named kind on the same sentence cannot stand in for the free-form one.
    """
    penalty = _CLAIMED_TITLE_PENALTY if expected.title is None and any(_title_matches(issue, t) for t in claimed) else 0
    same_title = _title_matches(issue, expected.title)
    quoted = normalize(expected.anchor) in _issue_text(issue)
    in_range = issue.start_line <= expected.line <= issue.end_line
    if same_title and quoted:
        tier = 0
    elif same_title and in_range:
        tier = 1
    elif quoted:
        tier = 2
    else:
        return None
    return tier * 2 + (0 if in_range else 1) + penalty


def ranked_hits(expected: ResolvedIssue, issues: Sequence[IssueItem], claimed: Sequence[str] = ()) -> list[int]:
    """Indices of the issues that report ``expected``, strongest evidence first (ties in issue order)."""
    scored = []
    for index, issue in enumerate(issues):
        tier = hit_tier(expected, issue, claimed)
        if tier is not None:
            scored.append((tier, index))
    return [index for _, index in sorted(scored)]


def hit_issue(expected: ResolvedIssue, issues: Sequence[IssueItem], claimed: Sequence[str] = ()) -> Optional[int]:
    """Index of the best-tier issue that reports this expected, or None."""
    ranked = ranked_hits(expected, issues, claimed)
    return ranked[0] if ranked else None


def claimed_titles(inventory: ResolvedInventory) -> tuple[str, ...]:
    """The titles the dataset's expected issues name, in this record or any other
    (see ``hit_tier``): a kind that has no expected issue in this record is still
    a kind, and a report of it is not the free-form one."""
    return tuple(sorted({*inventory.named_titles, *(e.title for e in inventory.expected_issues if e.title)}))


def decoy_hits(decoys: Sequence[Decoy], issues: Sequence[IssueItem], lines: Sequence[str] = ()) -> list[Decoy]:
    """The decoys a run flagged. An untitled decoy is flagged by any issue that
    quotes it. A titled one only by an issue under that title that quotes it or
    brackets one of the ``lines`` it is on, since a correct run may report the
    same sentence under another title."""

    def flags(decoy: Decoy, issue: IssueItem) -> bool:
        anchor = normalize(decoy.anchor)
        if decoy.title is None:
            return anchor in _issue_text(issue)
        if not _title_matches(issue, decoy.title):
            return False
        on = [n for n, line in enumerate(lines, 1) if anchor in normalize(line)]
        return anchor in _issue_text(issue) or any(issue.start_line <= n <= issue.end_line for n in on)

    return [d for d in decoys if any(flags(d, issue) for issue in issues)]


def edits_for(expected: ResolvedIssue, issue: IssueItem) -> list[ProposedEdit]:
    """The issue's edits that quote this expected's sentence.

    Matched on text, never on line alone: a paragraph-level issue carries the
    edits for every sentence on that line, and each must be judged against
    its own expected.
    """
    return [e for e in issue.edits if overlaps(expected.anchor, e.original_text)]


def fraction(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else NOT_APPLICABLE


def _tokens(text: str) -> list[str]:
    numbers = [value + ("%" if unit else "") for value, unit in _NUMBER_RE.findall(text)]
    return sorted(numbers + _FOOTNOTE_RE.findall(text) + _CITATION_RE.findall(text))


# A sentence ends at ., ! or ? (with any footnote markers that follow it) before
# whitespace and a capital, digit, quote or bracket, so decimals ("2.1 percent") and
# "et al., 2024" do not split it and "planners.[[4]](#footnote-5) Categories" does; a
# few abbreviations that take a capital after them ("et al. The", "e.g. The") are
# excluded by name.
_SENTENCE_BREAK_RE = re.compile(r"[.!?]+(?:\[\[\d+\]\]\(#footnote-\d+\))*(?=\s+[A-Z0-9\"“(\[])")
_NOT_A_SENTENCE_END = ("al", "e.g", "i.e", "vs", "cf", "Fig", "No")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENTENCE_BREAK_RE.finditer(text):
        before = text[:m.start()]
        if any(before.endswith(abbr) and (len(before) == len(abbr) or not before[-len(abbr) - 1].isalpha()) for abbr in _NOT_A_SENTENCE_END):
            continue
        spans.append((start, m.end()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def _soft(text: str) -> str:
    """Whitespace as the app's edit anchoring sees it: no-break spaces and runs of
    whitespace become one space, so a quote the app accepted is found here too."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " "))


def _edited_sentences(line_text: str, edits: Sequence[ProposedEdit]) -> Optional[str]:
    """The sentence(s) of ``line_text`` that the edits produce, with every edit applied.

    Edits are applied in turn to the line, each replacement's position kept
    current as later edits change the text before it. The sentences that
    overlap a replacement are returned joined. A deletion leaves nothing to
    judge and contributes no sentence: its neighbours were not edited. None
    when no edit's original text is found on the line, in which case only the
    replacements themselves can be judged.
    """
    applied = _soft(line_text)
    spans: list[tuple[int, int]] = []
    found = False
    for e in edits:
        original, replacement = _soft(e.original_text), _soft(e.replacement_text)
        at = applied.find(original)
        if at < 0:
            continue
        found = True
        shift = len(replacement) - len(original)
        spans = [(s + shift, t + shift) if s >= at + len(original) else (s, t) for s, t in spans]
        applied = applied[:at] + replacement + applied[at + len(original):]
        if replacement:
            spans.append((at, at + len(replacement)))
    if not found:
        return None
    touched = [
        applied[s:t].strip()
        for s, t in _sentence_spans(applied)
        if any(s < end and start < t for start, end in spans)
    ]
    return " ".join(touched)


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

    def line_of(e: ProposedEdit) -> str:
        """The line an edit is checked against: its own start_line when it names one
        inside the document (an issue may edit several occurrences on several lines),
        else the expected issue's line."""
        if 0 < e.start_line <= len(lines) and e.start_line != expected.line:
            return lines[e.start_line - 1]
        return lines[expected.line - 1] if 0 < expected.line <= len(lines) else ""

    line_text = lines[expected.line - 1] if 0 < expected.line <= len(lines) else ""
    on_line = [float(normalize(e.original_text) in normalize(line_of(e))) for e in edits]
    out["edit_quote_on_line"] = (fraction(on_line), f"{expected.id}: {int(sum(on_line))}/{len(edits)} quotes found verbatim on their line")

    if expected.edit is not None:
        # Phrases are judged on the sentence the edits produce: each replacement plus the
        # sentence(s) of the line they land in, with every one of the issue's edits applied.
        # Word-level edits ("Respondents" for "Participants") thus still carry a phrase written
        # against the whole sentence, an untouched neighbouring sentence cannot supply it, and a
        # forbidden phrase left standing in the edited sentence still fails.
        ok = []
        for e in edits:
            same_line = [o for o in edits if line_of(o) == line_of(e)]
            edited = _edited_sentences(line_of(e), same_line)
            scope = normalize(edited) if edited is not None else None
            repl = normalize(e.replacement_text)
            seen = repl if scope is None else repl + " " + scope
            missing = [p for p in expected.edit.must_include if normalize(p) not in seen]
            forbidden = [p for p in expected.edit.must_not_include if normalize(p) in seen]
            ok.append(float(not missing and not forbidden))
        out["edit_expected_phrases"] = (fraction(ok), f"{expected.id}: {int(sum(ok))}/{len(edits)} replacements carry the expected phrasing")

    kept = [float(_tokens(e.original_text) == _tokens(e.replacement_text)) for e in edits]
    out["edit_keeps_numbers_and_markers"] = (fraction(kept), f"{expected.id}: {int(sum(kept))}/{len(edits)} replacements keep every number, footnote marker and citation")

    clean = [float(not (_stranded(e.replacement_text) - _stranded(e.original_text))) for e in edits]
    out["edit_punctuation"] = (fraction(clean), f"{expected.id}: {int(sum(clean))}/{len(edits)} replacements add no stranded punctuation")

    for name, check in (extra or {}).items():
        verdicts = [check(e) for e in edits]
        results = [float(v) for v in verdicts if v is not None]
        if not results:
            continue  # nothing this check could assess here; the key stays NaN
        skipped = len(verdicts) - len(results)
        detail = f"{expected.id}: {int(sum(results))}/{len(results)} replacements pass {name}"
        out[f"edit_{name}"] = (fraction(results), detail + (f" ({skipped} not assessable)" if skipped else ""))
    return out


def hit_pairs(
    issues: Sequence[IssueItem], inventory: ResolvedInventory, one_to_one: bool = False
) -> tuple[dict[str, Optional[int]], list[tuple[ResolvedIssue, IssueItem]]]:
    """Which reported issue covers each expected one. The single pairing every
    layer uses, deterministic and judged alike, so they never grade different
    reports for the same expected issue.

    By default several expected issues may share a reported issue (a check
    that reports one issue per paragraph). With ``one_to_one`` a reported
    issue covers at most one expected issue, in inventory order, so a run
    that merges two occurrences the workflow must report separately leaves
    the second one missing.
    """
    # Match over the issues in canonical order, so a tie between two reports
    # with the same evidence is settled by their content, not by the order the
    # workflow happened to report them in; then map back to the original indices.
    order = _canonical_order(issues)
    ordered = [issues[i] for i in order]
    claimed = claimed_titles(inventory)
    if one_to_one:
        found = _one_to_one_hits(ordered, inventory.expected_issues, claimed)
    else:
        found = {e.id: hit_issue(e, ordered, claimed) for e in inventory.expected_issues}
    hits = {eid: (order[i] if i is not None else None) for eid, i in found.items()}
    pairs = [(e, issues[i]) for e in inventory.expected_issues if (i := hits[e.id]) is not None]
    return hits, pairs


def _canonical_order(issues: Sequence[IssueItem]) -> list[int]:
    """Indices of ``issues`` in a total order over their content: line range,
    title, description, then severity and suggested action. Identical reports
    therefore pair identically however the workflow ordered them. Severity
    comes late and is compared as plain text, independent of the expected
    severity, so it cannot steer a tie towards the right answer."""

    def key(i: int) -> tuple[int, int, str, str, str, str]:
        issue = issues[i]
        return (
            issue.start_line,
            issue.end_line,
            normalize(issue.title),
            normalize(issue.description),
            issue.severity,
            normalize(issue.suggested_action or ""),
        )

    return sorted(range(len(issues)), key=key)


# Cost of leaving an expected issue unmatched in the assignment problem below:
# larger than any total of tier costs, so cardinality is maximised first and
# evidence strength decides among pairings of equal size. Leaving a required
# issue unmatched costs more than leaving an optional one, so when one report
# could cover either, the required one gets it and recall is not lowered by a
# borderline expectation.
_UNMATCHED_OPTIONAL = 10_000
_UNMATCHED_REQUIRED = 20_000


def _one_to_one_hits(
    issues: Sequence[IssueItem], expected_issues: Sequence[ResolvedIssue], claimed: Sequence[str] = ()
) -> dict[str, Optional[int]]:
    """A one-to-one matching of expected issues to reported issues that covers
    as many expected issues as any pairing can and, among those, uses the
    strongest evidence (lowest total tier). Solved as an assignment problem;
    exact ties fall to the order given, which ``hit_pairs`` makes canonical."""
    size = max(len(expected_issues), len(issues))
    if size == 0:
        return {}
    unmatched = [_UNMATCHED_REQUIRED if e.required else _UNMATCHED_OPTIONAL for e in expected_issues]
    unmatched += [_UNMATCHED_OPTIONAL] * (size - len(expected_issues))  # padding rows
    cost = [[unmatched[row]] * size for row in range(size)]
    for row, e in enumerate(expected_issues):
        for col, issue in enumerate(issues):
            tier = hit_tier(e, issue, claimed)
            if tier is not None:
                cost[row][col] = tier
    assignment = _min_cost_assignment(cost)
    hits: dict[str, Optional[int]] = {}
    for row, e in enumerate(expected_issues):
        matched = assignment.get(row)
        hits[e.id] = matched if matched is not None and cost[row][matched] < _UNMATCHED_OPTIONAL else None
    return hits


def _min_cost_assignment(cost: list[list[int]]) -> dict[int, int]:
    """Hungarian algorithm (Kuhn-Munkres with potentials) on a square cost
    matrix: the row-to-column assignment of minimum total cost."""
    n = len(cost)
    inf = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)  # p[col] = row matched to col (1-indexed), 0 = none
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    return {p[j] - 1: j - 1 for j in range(1, n + 1) if p[j]}


def issue_detection_scores(
    issues: Sequence[IssueItem],
    inventory: ResolvedInventory,
    edits: bool = True,
    one_to_one: bool = False,
    titles: bool = True,
) -> tuple[dict[str, float], str]:
    """Detection and, for a workflow that proposes edits, generic edit hygiene.

    Keys: ``issue_check_keys(edits, titles)``; NaN where a sample gives a key
    nothing to judge. A workflow that never proposes edits passes
    ``edits=False``, and one whose inventory names no titles ``titles=False``,
    so its scores (and the log viewer's columns) carry no keys it can never
    score. ``one_to_one`` holds a workflow that must report each expected issue
    separately to that (see ``pairs``).
    """
    lines = inventory.document.split("\n")
    expected_issues = inventory.expected_issues
    values: dict[str, float] = {key: NOT_APPLICABLE for key in issue_check_keys(edits, titles)}
    notes: list[str] = []

    hits, pairs = hit_pairs(issues, inventory, one_to_one)
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
        merged = [e.id for e in required if hits[e.id] is None and one_to_one and hit_issue(e, issues) is not None]
        notes.append(f"recall {len(found_required)}/{len(required)}" + (f" (missing {', '.join(missing)})" if missing else ""))
        if merged:
            notes.append(f"merged into an issue that already covers another expected issue: {', '.join(merged)}")
        notes.append(f"precision {len(hit_indices)}/{len(issues)} issues matched an expected issue")
    else:
        values["clean_document_untouched"] = float(not issues)
        notes.append("clean document: " + ("nothing reported" if not issues else f"{len(issues)} issue(s) reported"))

    if pairs:
        if titles:
            values["title_correct"] = fraction([float(_title_matches(i, e.title)) for e, i in pairs if e.title])
        values["severity_correct"] = fraction([float(i.severity == e.severity) for e, i in pairs if e.severity])
        values["anchor_in_range"] = fraction([float(i.start_line <= e.line <= i.end_line) for e, i in pairs])
        notes += [f"{e.id}: reported as {i.title!r}, not under {e.title!r}" for e, i in pairs if e.title and not _title_matches(i, e.title)]
        notes += [f"{e.id}: severity {i.severity}, expected {e.severity}" for e, i in pairs if e.severity and i.severity != e.severity]
        notes += [f"{e.id}: lines {i.start_line}-{i.end_line} do not bracket line {e.line}" for e, i in pairs if not i.start_line <= e.line <= i.end_line]
    if pairs and edits:
        collected: dict[str, list[float]] = {}
        for e, i in pairs:
            for key, (value, detail) in edit_checks(e, i, lines).items():
                collected.setdefault(key, []).append(value)
                if value < 1.0:
                    notes.append(detail)
        for key, vals in collected.items():
            values[key] = fraction(vals)

    return values, " | ".join(notes) if notes else "all checks passed"


def extra_edit_scores(
    issues: Sequence[IssueItem],
    inventory: ResolvedInventory,
    checks: Mapping[str, EditCheck],
    one_to_one: bool = False,
) -> tuple[dict[str, float], str]:
    """A workflow's own per-edit checks, keyed ``edit_<name>``, over the edits of detected expected issues."""
    lines = inventory.document.split("\n")
    values: dict[str, float] = {f"edit_{name}": NOT_APPLICABLE for name in checks}
    notes: list[str] = []
    collected: dict[str, list[float]] = {}
    for e, i in hit_pairs(issues, inventory, one_to_one)[1]:
        results = edit_checks(e, i, lines, checks)
        for name in checks:
            key = f"edit_{name}"
            if key in results:
                value, detail = results[key]
                collected.setdefault(key, []).append(value)
                if value < 1.0:
                    notes.append(detail)
    for key, vals in collected.items():
        values[key] = fraction(vals)
    return values, " | ".join(notes) if notes else "all checks passed"


def decoy_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory, reasons: Sequence[str]
) -> tuple[dict[str, float], str]:
    """False positives by reason: ``no_fp_<reason>`` is 1 when no decoy of that
    reason was flagged, 0 when one was, NaN when the sample has no such decoy.

    ``reasons`` is the dataset-wide list, so every sample returns the same keys.
    """
    present = {d.reason for d in inventory.decoys}
    hit = decoy_hits(inventory.decoys, issues, inventory.document.split("\n"))
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
def issue_checks(edits: bool = True, one_to_one: bool = False, titles: bool = True) -> Scorer:
    """Reported issues against the expected ones: recall, precision, F0.5, lines,
    titles unless ``titles`` is False (an inventory that names none), plus edit
    presence and text integrity unless ``edits`` is False (a workflow that
    proposes no edits). ``one_to_one`` makes a reported issue cover at most one
    expected issue, for a workflow that must report each occurrence separately.
    The same keys for every sample of an eval."""
    return deterministic_scorer(
        lambda issues, inventory: issue_detection_scores(issues, inventory, edits, one_to_one, titles)
    )


@scorer(metrics=PER_KEY_METRICS)
def decoy_checks(reasons: Sequence[str]) -> Scorer:
    """False positives by decoy reason, ``no_fp_<reason>``.

    ``reasons`` is the dataset-wide list, so every sample's score carries the
    same keys, which Inspect requires of dict-valued scores.
    """
    return deterministic_scorer(lambda issues, inventory: decoy_scores(issues, inventory, reasons))
