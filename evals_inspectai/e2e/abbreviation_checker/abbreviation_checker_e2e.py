import json
from pathlib import Path
from typing import Any, List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, MemoryDataset, Sample, json_dataset
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    mean,
    metric,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field, ValidationError

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import (
    api_workflow_agent,
    api_workflow_agent_file,
    api_workflow_agent_file_cached,
)
from evals_inspectai.common.scorers import model_graded_check

from evals_inspectai.e2e.abbreviation_checker.fixtures import (
    document_files,
    entry_samples,
)


class AbbreviationItem(BaseModel):
    """Local mirror of the API response schema."""

    abbr: str
    inline_definition: str = ""
    occurrence_number: int = 0
    line_start: int = 0
    line_end: int = 0
    abbreviations_section_definition: Optional[str] = None
    ignored: bool = False
    ignored_reason: Optional[str] = None


class AbbreviationCheckOutput(BaseModel):
    """Local mirror of the API response schema."""

    abbreviations: List[AbbreviationItem] = Field(default_factory=list)
    abbreviations_section_found: bool = False
    reasoning: str = ""


# Fields compared per matched abbreviation entry.
_COMPARE_FIELDS = [
    "inline_definition",
    "line_start",
    "line_end",
    "abbreviations_section_definition",
    "ignored",
]


@task
def abbreviation_checker_e2e(
    backend: str = "remote",
    api_base_url: str | None = None,
) -> Task:
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        FieldSpec(
            target="target_answer",
            metadata=["target_abbreviations_section_found", "target_abbreviations"],
        ),
    )
    return Task(
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "abbreviation_scan_v2",
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=[
            abbreviation_list(),
            abbreviations_section_found(),
            model_graded_check(partial_credit=True),
        ],
    )


@task
def abbreviation_checker_from_files(
    data_dir: str | None = None,
    timeout_s: float = 1800,
    reference_path: str | None = None,
    backend: str = "remote",
    api_base_url: str | None = None,
) -> Task:
    """Run abbreviation_scan_v2 against every supported file in data_dir.

    When ``reference_path`` points at a references.json file (keyed by
    filename), each sample is scored against its reference entry.  Without a
    reference the task falls back to ``capture_output()`` so raw outputs can
    be collected for building new references.

    Args:
        data_dir: Directory to scan. Defaults to the ``data/`` folder next to
            this file. Supports Markdown, DOCX, DOC, and PDF; prefers Markdown
            when a source document and its Markdown snapshot share a stem.
        timeout_s: Seconds to wait for each workflow to complete (default 1800).
        reference_path: Path to a references.json file. Relative paths are
            resolved against the project root.
    """
    _eval_dir = Path(__file__).resolve().parent

    if data_dir:
        p = Path(data_dir)
        dir_path = p if p.is_absolute() else (_eval_dir.parents[2] / p)
    else:
        dir_path = _eval_dir / "data"

    resolved_ref_path: Path | None = None
    if reference_path:
        rp = Path(reference_path)
        resolved_ref_path = rp if rp.is_absolute() else (_eval_dir.parents[2] / rp)
    else:
        default_ref = dir_path / "references.json"
        if default_ref.exists():
            resolved_ref_path = default_ref

    ref_keys: set[str] = set()
    if resolved_ref_path:
        ref_keys = set(json.loads(resolved_ref_path.read_text()).keys())

    files = document_files(dir_path)
    if not files:
        raise ValueError(f"No supported documents in {dir_path}")
    if resolved_ref_path:
        missing = [f.name for f in files if f.name not in ref_keys]
        if missing:
            raise ValueError(f"Missing references for: {', '.join(missing)}")

    samples = [
        Sample(
            id=f.name,
            input=str(f.resolve()),
            metadata=_reference_metadata(
                f.name,
                (
                    str(resolved_ref_path)
                    if (resolved_ref_path and f.name in ref_keys)
                    else None
                ),
            ),
        )
        for f in files
    ]

    has_references = bool(resolved_ref_path and any(f.name in ref_keys for f in files))
    scorers: Any = (
        [abbreviation_list(), abbreviations_section_found()]
        if has_references
        else capture_output()
    )

    return Task(
        dataset=MemoryDataset(samples),
        fail_on_error=0.2,
        solver=api_workflow_agent_file(
            "abbreviation_scan_v2",
            timeout_s=timeout_s,
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=scorers,
    )


@task
def abbreviation_checker_entries(
    data_dir: str | None = None,
    timeout_s: float = 1800,
    reference_path: str | None = None,
    filename: str | None = None,
    backend: str = "remote",
    api_base_url: str | None = None,
) -> Task:
    """One Inspect sample per distinct reference abbreviation.

    Runs the workflow once per file and epoch, then scores each reference entry
    as a group so every abbreviation appears as one pass/fail row in the log.
    Each row reports its occurrences, first-use definition, and errors.

    Requires a references.json file (auto-detected from ``data/`` or via
    ``reference_path``). Missing references fail before workflow invocation;
    use ``abbreviation_checker_from_files`` to collect unscored outputs.

    Args:
        data_dir: Directory to scan for supported files.
        timeout_s: Seconds to wait for each workflow to complete.
        reference_path: Path to a references.json file (relative to project root).
        filename: Optional single filename from ``data_dir``. Use this when a
            flow needs one eval task and log per document.
    """
    _eval_dir = Path(__file__).resolve().parent

    if data_dir:
        p = Path(data_dir)
        dir_path = p if p.is_absolute() else (_eval_dir.parents[2] / p)
    else:
        dir_path = _eval_dir / "data"

    resolved_ref_path: Path | None = None
    if reference_path:
        rp = Path(reference_path)
        resolved_ref_path = rp if rp.is_absolute() else (_eval_dir.parents[2] / rp)
    else:
        default_ref = dir_path / "references.json"
        if default_ref.exists():
            resolved_ref_path = default_ref

    _backend = local_backend_for(backend, api_base_url)

    files = document_files(dir_path, filename)

    samples = entry_samples(files, resolved_ref_path or dir_path / "references.json")

    output_cache: dict[str, Any] = {}

    return Task(
        dataset=MemoryDataset(samples),
        fail_on_error=0.2,
        solver=api_workflow_agent_file_cached(
            "abbreviation_scan_v2",
            output_cache,
            timeout_s=timeout_s,
            local_backend=_backend,
            api_base_url=api_base_url,
        ),
        scorer=single_entry_scorer(),
    )


def _reference_metadata(filename: str, ref_path: str | None) -> dict[str, Any]:
    """Minimal metadata stored per sample — just enough for the scorer to load
    the reference at score time. The full abbreviation list lives in the file."""
    if ref_path is None:
        return {}
    ref = json.loads(Path(ref_path).read_text()).get(filename, {})
    return {
        "reference_file": ref_path,
        "reference_key": filename,
        "target_abbreviations_section_found": str(
            ref.get("abbreviations_section_found", False)
        ),
    }


@scorer(metrics=[mean(), stderr()])
def abbreviation_list() -> Scorer:
    """Score: fraction of reference entries found and correctly characterised.

    Entries are matched by (abbr, line_start) so the score is stable across
    runs that find additional abbreviations or use different occurrence numbers.
    """

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = AbbreviationCheckOutput.model_validate_json(
                state.output.completion
            )
        except ValidationError as e:
            return Score(value=0.0, explanation=f"Parse error: {e}")
        s = _compare_abbreviation_list(output, state)
        return s

    return score


@scorer(metrics=[mean(), stderr()])
def abbreviations_section_found() -> Scorer:
    """Score: CORRECT when abbreviations_section_found matches the reference."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            output = AbbreviationCheckOutput.model_validate_json(
                state.output.completion
            )
        except ValidationError as e:
            return Score(value=INCORRECT, explanation=f"Parse error: {e}")
        matched = _compare_abbreviations_section_found(output, state)
        expected = state.metadata.get("target_abbreviations_section_found", "")
        return Score(
            value=CORRECT if matched else INCORRECT,
            explanation=f"Got {output.abbreviations_section_found}, expected {expected}",
        )

    return score


@scorer(metrics=[mean(), stderr()])
def capture_output() -> Scorer:
    """Pass-through scorer that always returns CORRECT; stores raw output for inspection."""

    async def score(state: TaskState, target: Target) -> Score:
        return Score(value=CORRECT, explanation=state.output.completion)

    return score


def _pooled_occurrence_counts(scores: list[SampleScore]) -> tuple[int, int, int]:
    """Return pooled (TP, FP, FN) occurrence counts from scorer metadata."""
    return (
        sum((item.score.metadata or {}).get("TP", 0) for item in scores),
        sum((item.score.metadata or {}).get("FP", 0) for item in scores),
        sum((item.score.metadata or {}).get("FN", 0) for item in scores),
    )


@metric
def occurrence_accuracy() -> Metric:
    """Pooled occurrence accuracy: TP / (TP + FP + FN).

    True negatives cannot be counted for an open-ended document scan: the
    evaluator has no finite list of every non-abbreviation candidate.
    """

    def compute(scores: list[SampleScore]) -> float:
        tp, fp, fn = _pooled_occurrence_counts(scores)
        denominator = tp + fp + fn
        return tp / denominator if denominator else 0.0

    return compute


@metric
def occurrence_precision() -> Metric:
    """Pooled occurrence precision: TP / (TP + FP)."""

    def compute(scores: list[SampleScore]) -> float:
        tp, fp, _ = _pooled_occurrence_counts(scores)
        return tp / (tp + fp) if tp + fp else 0.0

    return compute


@metric
def occurrence_recall() -> Metric:
    """Pooled occurrence recall: TP / (TP + FN)."""

    def compute(scores: list[SampleScore]) -> float:
        tp, _, fn = _pooled_occurrence_counts(scores)
        return tp / (tp + fn) if tp + fn else 0.0

    return compute


@scorer(metrics=[occurrence_accuracy(), occurrence_precision(), occurrence_recall()])
def single_entry_scorer() -> Scorer:
    """Score each reference occurrence against the full workflow output.

    Expects ``target.text`` to be a JSON-encoded list of occurrence dicts and
    ``state.output.completion`` to be the full workflow state JSON.  Used by
    ``abbreviation_checker_entries`` so each distinct abbreviation gets one
    informative pass/fail row in the Inspect log.
    """

    async def score(state: TaskState, target: Target) -> Score:
        expected_entries = json.loads(target.text)
        if isinstance(expected_entries, dict):
            expected_entries = [expected_entries]
        expected_entries = [
            entry for entry in expected_entries if not entry.get("ignored", False)
        ]
        if not expected_entries:
            return Score(
                value=1.0,
                explanation="Ignored occurrence; excluded from scoring",
                metadata={
                    "TOTAL": 0,
                    "TP": 0,
                    "FP": 0,
                    "TN": None,
                    "FN": 0,
                    "characterization": {},
                },
            )

        try:
            output = AbbreviationCheckOutput.model_validate_json(
                state.output.completion
            )
        except ValidationError as e:
            denominator = len(expected_entries)
            return Score(
                value=0.0,
                explanation=f"Parse error: {e}",
                metadata={
                    "TOTAL": denominator,
                    "TP": 0,
                    "FP": 0,
                    "TN": None,
                    "FN": denominator,
                    "characterization": {},
                },
            )

        abbr = expected_entries[0]["abbr"]
        actual_entries = [
            item
            for item in output.abbreviations
            if item.abbr == abbr and not item.ignored
        ]
        matched, comparison_errors, additional = _compare_abbreviation_occurrences(
            expected_entries, actual_entries
        )
        # Charge unknown abbreviations once, on the first reference row, so
        # pooled counts do not multiply these errors across every sample.
        document_extras = _unreferenced_actual_occurrences(output, state, abbr)
        compliance_errors = _abbreviation_compliance_errors(actual_entries)
        occurrence_errors = [
            *comparison_errors,
            *(
                {
                    "type": "extra_occurrence",
                    "line": entry["line_start"],
                    "actual": entry,
                }
                for entry in additional
            ),
            *(
                {
                    "type": "unrecognised_document_occurrence",
                    "line": entry["line_start"],
                    "actual": entry,
                }
                for entry in document_extras
            ),
        ]
        # An incorrect annotation is both a missing exact reference match and
        # an incorrect prediction; otherwise precision ignores wrong definitions.
        mismatched = sum(
            error["type"] == "field_mismatch" for error in comparison_errors
        )
        entry_false_positives = len(additional) + mismatched
        false_negatives = len(expected_entries) - matched
        false_positives = entry_false_positives + len(document_extras)
        metric_denominator = matched + false_positives + false_negatives
        score_value = matched / metric_denominator if metric_denominator else 1.0
        precision = (
            matched / (matched + false_positives) if matched + false_positives else 0.0
        )
        recall = (
            matched / (matched + false_negatives) if matched + false_negatives else 0.0
        )
        detail = _abbreviation_detail(
            abbr,
            expected_entries,
            actual_entries,
            occurrence_errors,
            compliance_errors,
            matched,
            comparison_errors,
            additional,
        )
        metadata: dict[str, Any] = {
            "TOTAL": metric_denominator,
            "TP": matched,
            "FP": false_positives,
            "TN": None,
            "FN": false_negatives,
            "characterization": {abbr: detail},
        }

        occurrence_text = (
            f"{abbr}: TOTAL={metric_denominator}; TP={matched}, FP={false_positives}, "
            f"TN=undefined, FN={false_negatives}"
        )
        occurrence_text += f"; precision={precision:.3f}, recall={recall:.3f}"
        if document_extras:
            occurrence_text += f"; includes {len(document_extras)} document-wide unknown occurrence(s), charged once"
        return Score(
            value=score_value,
            explanation=(
                occurrence_text + f"; {len(occurrence_errors)} occurrence error(s)"
            ),
            metadata=metadata,
        )

    return score


def _unreferenced_actual_occurrences(
    output: AbbreviationCheckOutput, state: TaskState, current_abbr: str
) -> list[dict[str, Any]]:
    """Charge wholly hallucinated abbreviations once per document."""
    refs = json.loads(Path(state.metadata["reference_file"]).read_text())
    expected_entries = refs.get(state.metadata["filename"], {}).get("abbreviations", [])
    expected_abbreviations = {entry["abbr"] for entry in expected_entries}
    applicable_abbreviations = {
        entry["abbr"] for entry in expected_entries if not entry.get("ignored", False)
    }
    if not applicable_abbreviations or current_abbr != min(applicable_abbreviations):
        return []
    return [
        item.model_dump()
        for item in output.abbreviations
        if not item.ignored and item.abbr not in expected_abbreviations
    ]


def _match_occurrences(
    expected: list[dict[str, Any]], actual: list[AbbreviationItem]
) -> tuple[list[AbbreviationItem | None], list[AbbreviationItem]]:
    """Reserve exact matches before pairing remaining items for diagnostics."""
    remaining = list(actual)
    matches: list[AbbreviationItem | None] = [None] * len(expected)
    for exact_only in (True, False):
        for index, entry in enumerate(expected):
            if matches[index] is not None:
                continue
            candidates = [
                item
                for item in remaining
                if (item.abbr, item.line_start)
                == (entry["abbr"], entry.get("line_start", 0))
                and (
                    not exact_only
                    or all(
                        entry.get(field) == getattr(item, field)
                        for field in _COMPARE_FIELDS
                    )
                )
            ]
            if candidates:
                match = _best_candidate(entry, candidates)
                matches[index] = match
                remaining.remove(match)
    return matches, remaining


def _compare_abbreviation_occurrences(
    expected_entries: list[dict[str, Any]],
    actual_entries: list[AbbreviationItem],
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Match occurrences without reusing actual items; do not penalize extras.

    ``occurrence_number`` is intentionally not compared after a candidate is
    selected. It is an ordinal produced by the detector, so one missed earlier
    occurrence shifts every later ordinal even when its location and document
    annotations are correct.
    """
    matches, remaining = _match_occurrences(expected_entries, actual_entries)
    errors: list[dict[str, Any]] = []
    matched = 0

    for expected, actual in zip(expected_entries, matches, strict=True):
        if actual is None:
            errors.append(
                {
                    "type": "missing_occurrence",
                    "line": expected.get("line_start", 0),
                    "expected": expected,
                }
            )
            continue

        diffs = {
            field: {"expected": expected.get(field), "actual": getattr(actual, field)}
            for field in _COMPARE_FIELDS
            if expected.get(field) != getattr(actual, field)
        }
        if diffs:
            errors.append(
                {
                    "type": "field_mismatch",
                    "line": expected.get("line_start", 0),
                    "diffs": diffs,
                }
            )
        else:
            matched += 1

    additional = [actual.model_dump() for actual in remaining]
    return matched, errors, additional


def _first_applicable_reference(
    entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    applicable = [entry for entry in entries if not entry.get("ignored", False)]
    return min(
        applicable,
        key=lambda entry: (
            entry.get("line_start", 0),
            entry.get("occurrence_number", 0),
        ),
        default=None,
    )


def _first_applicable_actual(
    entries: list[AbbreviationItem],
) -> AbbreviationItem | None:
    applicable = [entry for entry in entries if not entry.ignored]
    return min(
        applicable,
        key=lambda entry: (entry.line_start, entry.occurrence_number),
        default=None,
    )


def _abbreviation_compliance_errors(
    actual_entries: list[AbbreviationItem],
) -> list[dict[str, Any]]:
    """Return only the two document-compliance errors this scorer grades."""
    first = _first_applicable_actual(actual_entries)
    if first is None and actual_entries:
        return []  # Every occurrence is ignored, so neither rule applies.

    errors: list[dict[str, Any]] = []
    if first is None or not first.inline_definition.strip():
        errors.append(
            {
                "type": "missing_first_use_definition",
                "message": "No definition at first use",
                "line": first.line_start if first else None,
            }
        )

    section_definition = next(
        (
            entry.abbreviations_section_definition
            for entry in actual_entries
            if entry.abbreviations_section_definition
            and entry.abbreviations_section_definition.strip()
        ),
        None,
    )
    if section_definition is None:
        errors.append(
            {
                "type": "missing_abbreviations_section_definition",
                "message": "No definition in the Abbreviations section",
            }
        )
    return errors


def _abbreviation_detail(
    abbr: str,
    expected_entries: list[dict[str, Any]],
    actual_entries: list[AbbreviationItem],
    errors: list[dict[str, Any]],
    compliance_errors: list[dict[str, Any]],
    matched: int,
    comparison_errors: list[dict[str, Any]],
    additional: list[dict[str, Any]],
) -> dict[str, Any]:
    first = _first_applicable_reference(expected_entries)
    first_actual = _first_applicable_actual(actual_entries)
    actual_definition = first_actual.inline_definition if first_actual else None
    expected_definition = first.get("inline_definition") if first else None
    section_definition = next(
        (
            entry.abbreviations_section_definition
            for entry in actual_entries
            if entry.abbreviations_section_definition
        ),
        None,
    )
    return {
        "abbreviation": abbr,
        "occurrences": {
            "expected_count": len(expected_entries),
            "actual_count": len(actual_entries),
            "expected": expected_entries,
            "actual": [item.model_dump() for item in actual_entries],
        },
        "definition": {
            "first_use_line": first_actual.line_start if first_actual else None,
            "expected": expected_definition,
            "actual": actual_definition,
            "abbreviations_section": section_definition,
            "applicable": first_actual is not None,
        },
        "errors": errors,
        "document_compliance_errors": compliance_errors,
        "occurrence_comparison": {
            "matched_reference_occurrences": matched,
            "reference_occurrence_count": len(expected_entries),
            "differences": comparison_errors,
            "additional_occurrences": additional,
            "penalized": True,
        },
    }


def _best_candidate(
    expected: dict[str, Any], candidates: list[AbbreviationItem]
) -> AbbreviationItem:
    """Pick the candidate that best matches the reference entry.

    When there is only one candidate the choice is trivial.  When several
    share the same (abbr, line_start) — e.g. four 2PL occurrences on one
    line — occurrence_number may have shifted between runs, so we rank by
    field similarity instead of blindly taking candidates[0]:

    1. Best field-similarity score across _COMPARE_FIELDS (fewest diffs, with
       inline_definition given extra weight because it is the most distinctive).
    2. Exact occurrence_number match only as a tiebreaker.
    """
    if len(candidates) == 1:
        return candidates[0]

    ref_occ = expected.get("occurrence_number", 0)

    def _similarity(c: AbbreviationItem) -> int:
        score = 0
        for f in _COMPARE_FIELDS:
            if expected.get(f) == getattr(c, f):
                score += 2 if f == "inline_definition" else 1
        return score

    return max(
        candidates, key=lambda c: (_similarity(c), c.occurrence_number == ref_occ)
    )


def _compare_abbreviations_section_found(
    output: AbbreviationCheckOutput, state: TaskState
) -> bool:
    return (
        str(output.abbreviations_section_found).lower()
        == state.metadata.get("target_abbreviations_section_found", "").lower()
    )


def _entry_key(abbr: str, line_start: int) -> str:
    return f"{abbr}@L{line_start}"


def _compare_abbreviation_list(
    output: AbbreviationCheckOutput, state: TaskState
) -> Score:
    """Compare output abbreviations against the reference using identity matching.

    Entries are matched by (abbr, line_start) rather than list position, so
    insertions in one part of the document do not cascade as diffs elsewhere.
    The score is the fraction of reference entries that were found with all
    compared fields correct; extra entries the model finds are surfaced in
    metadata but not penalised.

    The returned ``Score.metadata`` is a hierarchical, extensible report:

        {
          "summary":  {matched, total, missing, mismatched, extra, score},
          "by_field": {field_name: mismatch_count, ...},   # where diffs cluster
          "missing":  [key, ...],                          # in ref, not in output
          "extra":    [key, ...],                          # in output, not in ref
          "mismatches": [{key, diffs: {field: [expected, actual]}}, ...],
        }
    """
    # Prefer loading from the reference file (file-based task); fall back to
    # metadata-embedded list (markdown task / legacy datasets).
    ref_file = state.metadata.get("reference_file")
    ref_key = state.metadata.get("reference_key")
    if ref_file and ref_key:
        refs = json.loads(Path(ref_file).read_text())
        expected = refs.get(ref_key, {}).get("abbreviations", [])
    else:
        expected = state.metadata.get("target_abbreviations", [])

    if not expected:
        return Score(value=1.0, explanation="No target abbreviations defined")

    matches, remaining = _match_occurrences(expected, output.abbreviations)
    matched = 0
    missing: list[str] = []
    mismatches: list[dict[str, Any]] = []
    by_field: dict[str, int] = {}

    for exp, act in zip(expected, matches, strict=True):
        k = (exp["abbr"], exp.get("line_start", 0))
        if act is None:
            missing.append(_entry_key(*k))
            continue
        diffs = {
            f: [exp.get(f), getattr(act, f)]
            for f in _COMPARE_FIELDS
            if exp.get(f) != getattr(act, f)
        }
        if not diffs:
            matched += 1
            continue
        for f in diffs:
            by_field[f] = by_field.get(f, 0) + 1
        mismatches.append({"key": _entry_key(*k), "diffs": diffs})

    extra = [_entry_key(item.abbr, item.line_start) for item in remaining]

    total = len(expected)
    score_val = matched / total if total else 1.0

    lines: list[str] = [
        f"{matched}/{total} matched  |  {len(mismatches)} field-mismatched  "
        f"|  {len(missing)} missing  |  {len(extra)} extra"
    ]

    if mismatches:
        lines.append("\nField mismatches:")
        for mm in mismatches[:20]:
            diff_parts = [f"{f}: {e!r} → {a!r}" for f, (e, a) in mm["diffs"].items()]
            lines.append(f"  {mm['key']}: " + " | ".join(diff_parts))
        if len(mismatches) > 20:
            lines.append(f"  … {len(mismatches) - 20} more")

    if missing:
        shown = ", ".join(missing[:12])
        suffix = f", … +{len(missing) - 12}" if len(missing) > 12 else ""
        lines.append(f"\nMissing: {shown}{suffix}")

    metadata: dict[str, Any] = {
        "summary": {
            "matched": matched,
            "total": total,
            "missing": len(missing),
            "mismatched": len(mismatches),
            "extra": len(extra),
            "score": round(score_val, 4),
        },
        "by_field": dict(sorted(by_field.items(), key=lambda kv: -kv[1])),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
    }

    return Score(value=score_val, explanation="\n".join(lines), metadata=metadata)
