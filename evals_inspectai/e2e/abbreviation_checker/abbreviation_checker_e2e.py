import json
from pathlib import Path
from typing import Any, List, Optional

from inspect_ai import Task, task
from inspect_ai.dataset import FieldSpec, MemoryDataset, Sample, json_dataset
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field, ValidationError

from evals_inspectai.common.backend import local_backend_for
from evals_inspectai.common.api_solver import (
    api_workflow_agent,
    api_workflow_agent_file_cached,
)
from evals_inspectai.common.comparers import deep_diff_score
from evals_inspectai.common.scorers import model_graded_check, structured_output_scorer
from evals_inspectai.e2e.abbreviation_checker.fixtures import document_files, entry_samples


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


@task
def abbreviation_checker_e2e(backend: str = "remote", api_base_url: str | None = None):
    dataset = json_dataset(
        str(Path(__file__).parent / "dataset.json"),
        FieldSpec(
            target="target_answer",
            metadata=["target_abbreviations_section_found", "target_abbreviations"],
        ),
    )
    return Task(
        # TODO: allow model to be specified dynamically / via api config
        dataset=dataset,
        fail_on_error=0.2,
        solver=api_workflow_agent(
            "abbreviation_scan_v2", item_messages_key="chunks", item_label="chunk",
            local_backend=local_backend_for(backend, api_base_url), api_base_url=api_base_url,
        ),
        scorer=[
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviation_list
            ),
            structured_output_scorer(
                AbbreviationCheckOutput, _compare_abbreviations_section_found
            ),
            model_graded_check(partial_credit=True),
        ],
    )


@task
def abbreviation_checker_variants(
    data_dir: str,
    reference_path: str | None = None,
    filename: str | None = None,
    timeout_s: float = 1800,
    backend: str = "remote",
    api_base_url: str | None = None,
) -> Task:
    """Score one sample per abbreviation, using the chunked workflow once per file."""
    directory = Path(data_dir).resolve()
    refs_path = Path(reference_path).resolve() if reference_path else directory / "references.json"
    if not refs_path.is_file():
        raise ValueError(f"Missing abbreviation references: {refs_path}")
    references = json.loads(refs_path.read_text(encoding="utf-8"))
    samples: list[Sample] = []
    for document in document_files(directory, filename):
        reference = references.get(document.name)
        if reference is None:
            raise ValueError(f"Missing reference for {document.name} in {refs_path}")
        groups: dict[str, list[dict[str, Any]]] = {}
        for entry in reference.get("abbreviations", []):
            if not entry.get("ignored", False):
                groups.setdefault(entry["abbr"], []).append(entry)
        if not groups:
            raise ValueError(f"No applicable abbreviations in {document.name}")
        for abbr, expected_entries in groups.items():
            samples.append(
                Sample(
                    id=f"{document.name}::{abbr}",
                    input=str(document.resolve()),
                    metadata={"abbr": abbr, "target_abbreviations": expected_entries},
                )
            )
    return Task(
        dataset=MemoryDataset(samples),
        fail_on_error=0.2,
        solver=api_workflow_agent_file_cached(
            "abbreviation_scan_v2",
            output_cache={},
            timeout_s=timeout_s,
            item_messages_key="chunks",
            item_label="chunk",
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=single_entry_scorer(),
    )


@task
def abbreviation_checker_entries(
    data_dir: str,
    reference_path: str | None = None,
    filename: str | None = None,
    timeout_s: float = 1800,
    backend: str = "remote",
    api_base_url: str | None = None,
) -> Task:
    """Score one sample per abbreviation; sample.target holds the JSON entry list."""
    directory = Path(data_dir).resolve()
    refs_path = Path(reference_path).resolve() if reference_path else directory / "references.json"
    samples = entry_samples(document_files(directory, filename), refs_path)
    return Task(
        dataset=MemoryDataset(samples),
        fail_on_error=0.2,
        solver=api_workflow_agent_file_cached(
            "abbreviation_scan_v2",
            output_cache={},
            timeout_s=timeout_s,
            item_messages_key="chunks",
            item_label="chunk",
            local_backend=local_backend_for(backend, api_base_url),
            api_base_url=api_base_url,
        ),
        scorer=single_entry_scorer(),
    )


abbreviation_checker_from_files = abbreviation_checker_entries


def _compare_abbreviations_section_found(
    output: AbbreviationCheckOutput, state: TaskState
) -> bool:
    """Deterministic: the "Abbreviations section found" boolean matches the target."""
    return (
        str(output.abbreviations_section_found).lower()
        == state.metadata.get("target_abbreviations_section_found", "").lower()
    )


_COMPARE_FIELDS = [
    "inline_definition",
    "line_start",
    "line_end",
    "abbreviations_section_definition",
    "ignored",
]


def _compare_abbreviation_occurrences(
    expected: list[dict[str, Any]],
    actual: list["AbbreviationItem"],
) -> tuple[int, list[dict[str, Any]], list["AbbreviationItem"]]:
    """Match expected vs actual occurrences, returning (matched, errors, additional).

    Matching runs in priority rounds so that exact content matches are reserved
    for the expected entries that need them (prevents an inexact match from
    consuming an actual that another expected could match exactly).

    Round 1: same line_start AND same inline_definition (exact).
    Round 2: same line_start only (definition may differ).
    Round 3: same inline_definition (non-empty) only.
    Round 4: same occurrence_number.

    A matched pair where all _COMPARE_FIELDS agree counts toward matched.
    A matched pair with field mismatches is recorded as a field_mismatch error.
    Unmatched expected entries become missing_occurrence errors.
    Remaining actual entries are returned as additional (FP).
    """
    remaining: list[tuple[int, "AbbreviationItem"]] = list(enumerate(actual))
    used: set[int] = set()
    assignments: list[tuple[dict[str, Any], int]] = []  # (exp, actual_index)
    unmatched_expected: list[dict[str, Any]] = []

    def _find(exp: dict[str, Any], candidates: list[tuple[int, "AbbreviationItem"]], key: Any) -> int | None:
        for idx, act in candidates:
            if key(exp, act):
                return idx
        return None

    rounds = [
        lambda e, a: a.line_start == e.get("line_start") and a.inline_definition == (e.get("inline_definition") or ""),
        lambda e, a: a.line_start == e.get("line_start"),
        lambda e, a: bool(e.get("inline_definition")) and a.inline_definition == e.get("inline_definition"),
        lambda e, a: a.occurrence_number == e.get("occurrence_number"),
    ]

    # Iterative round-based matching: each round only claims what hasn't been matched yet.
    remaining_expected = list(expected)
    for match_round in rounds:
        still_unmatched: list[dict[str, Any]] = []
        available = [(idx, act) for idx, act in remaining if idx not in used]
        for exp in remaining_expected:
            idx = _find(exp, available, match_round)
            if idx is not None:
                used.add(idx)
                available = [(i, a) for i, a in available if i != idx]
                assignments.append((exp, idx))
            else:
                still_unmatched.append(exp)
        remaining_expected = still_unmatched

    unmatched_expected = remaining_expected

    errors: list[dict[str, Any]] = []
    matched = 0
    for exp, act_idx in assignments:
        act = actual[act_idx]
        mismatches = [
            {"field": f, "expected": exp.get(f), "actual": getattr(act, f, None)}
            for f in _COMPARE_FIELDS
            if exp.get(f) != getattr(act, f, None)
        ]
        if mismatches:
            errors.append({"type": "field_mismatch", "expected": exp, "mismatches": mismatches})
        else:
            matched += 1

    for exp in unmatched_expected:
        errors.append({"type": "missing_occurrence", "expected": exp})

    additional = [actual[idx] for idx in range(len(actual)) if idx not in used]
    return matched, errors, additional


def _pooled_occurrence_counts(
    sample_scores: list[Any],
) -> tuple[int, int, int]:
    """Sum TP, FP, FN across sample scores that carry those metadata keys."""
    tp = sum(s.score.metadata["TP"] for s in sample_scores)
    fp = sum(s.score.metadata["FP"] for s in sample_scores)
    fn = sum(s.score.metadata["FN"] for s in sample_scores)
    return tp, fp, fn


@scorer(metrics=[mean(), stderr()])
def single_entry_scorer() -> Scorer:
    """Per-abbreviation scorer: TP / (TP + FP + FN) for this abbreviation's occurrences.

    Score metadata carries TP, FP, FN, TOTAL (abbreviation-level) and UNKNOWN_FP
    (occurrences of this abbreviation that appear in the output but whose abbr is
    absent from the reference — an error-condition counter, normally 0).
    """

    async def score(state: TaskState, target: Target) -> Score:
        def _fail(reason: str) -> Score:
            return Score(
                value=0.0,
                explanation=reason,
                metadata={"TOTAL": 0, "TP": 0, "FP": 0, "FN": 0, "UNKNOWN_FP": 0},
            )

        try:
            output = AbbreviationCheckOutput.model_validate_json(state.output.completion)
        except (ValidationError, Exception) as exc:
            return _fail(f"Parse error: {exc}")

        try:
            expected: list[dict[str, Any]] = json.loads(target.text)
        except Exception as exc:
            return _fail(f"Target parse error: {exc}")

        abbr = (state.metadata or {}).get("abbr") or (expected[0]["abbr"] if expected else "")
        actual_for_abbr = [item for item in output.abbreviations if item.abbr == abbr and not item.ignored]

        matched, errors, additional = _compare_abbreviation_occurrences(expected, actual_for_abbr)

        wrong = sum(1 for err in errors if err["type"] == "field_mismatch")
        missing = sum(1 for err in errors if err["type"] == "missing_occurrence")
        tp = matched
        fn = missing + wrong
        fp_abbr = len(additional) + wrong
        total = tp + fp_abbr + fn
        occurrence_accuracy = tp / total if total > 0 else 1.0

        # Document-wide unknowns tracked separately — not folded into occurrence_accuracy.
        fp_unknowns = 0
        unknown_lines: list[str] = []
        reference_file = (state.metadata or {}).get("reference_file")
        filename = (state.metadata or {}).get("filename")
        if reference_file and filename:
            try:
                refs = json.loads(Path(reference_file).read_text(encoding="utf-8"))
                known = {e["abbr"] for e in refs.get(filename, {}).get("abbreviations", [])}
                unknowns = [item for item in output.abbreviations if item.abbr == abbr and item.abbr not in known and not item.ignored]
                fp_unknowns = len(unknowns)
                if unknowns:
                    unknown_lines = [f"  {u.abbr} (line {u.line_start})" for u in unknowns]
            except Exception:
                pass

        # Build explanation
        first = min(expected, key=lambda entry: entry.get("occurrence_number", 0)) if expected else {}
        abbr_section_def = first.get("abbreviations_section_definition") or ""
        def_at_first_use = first.get("inline_definition") or ""

        # Explanation: narrative only — raw counts live in metadata.
        lines: list[str] = [
            f"{abbr} — {len(expected)} expected occurrence(s)",
            f"Abbr section: {'yes, ' + repr(abbr_section_def) if abbr_section_def else 'no'}",
            f"First-use definition: {def_at_first_use!r}" if def_at_first_use else "First-use definition: (none)",
        ]

        if errors:
            lines.append("Issues:")
            for err in errors:
                exp_entry = err["expected"]
                loc = f"occ {exp_entry.get('occurrence_number')} line {exp_entry.get('line_start')}"
                if err["type"] == "missing_occurrence":
                    lines.append(f"  {loc} — missing from output")
                else:
                    detail = "; ".join(f"{m['field']}: expected {m['expected']!r}, got {m['actual']!r}" for m in err["mismatches"])
                    lines.append(f"  {loc} — {detail}")

        if additional:
            lines.append("Extra (not in reference):")
            for a in additional:
                lines.append(f"  occ {a.occurrence_number} line {a.line_start}")

        if unknown_lines:
            lines.append(f"Document-wide unknowns ({fp_unknowns}):")
            lines.extend(unknown_lines)

        return Score(
            value=occurrence_accuracy,
            explanation="\n".join(lines),
            metadata={"TOTAL": total, "TP": tp, "FP": fp_abbr, "FN": fn, "UNKNOWN_FP": fp_unknowns},
        )

    return score


def _compare_variant_entry(
    output: AbbreviationCheckOutput, state: TaskState
) -> Score:
    """Per-abbreviation scorer showing TP/FN/FP at the occurrence level."""
    abbr = state.metadata["abbr"]
    expected: list[dict[str, Any]] = state.metadata["target_abbreviations"]

    actual_by_occ: dict[int, AbbreviationItem] = {
        item.occurrence_number: item
        for item in output.abbreviations
        if item.abbr == abbr and not item.ignored
    }
    expected_by_occ: dict[int, dict[str, Any]] = {
        e["occurrence_number"]: e for e in expected
    }

    # Abbreviation-level summary from the first expected entry
    first_expected = min(expected, key=lambda e: e["occurrence_number"])
    abbr_section_def = first_expected.get("abbreviations_section_definition") or ""
    definition_at_first_use = first_expected.get("inline_definition") or ""

    tp: list[str] = []
    fn: list[str] = []
    fp: list[str] = []

    for occ_num, exp in sorted(expected_by_occ.items()):
        act = actual_by_occ.get(occ_num)
        if act is None:
            fn.append(f"  occ {occ_num} (line {exp.get('line_start')}) — missing from output")
            continue
        mismatches = []
        for field in _COMPARE_FIELDS:
            exp_val = exp.get(field)
            act_val = getattr(act, field, None)
            if exp_val != act_val:
                mismatches.append(f"{field}: expected {exp_val!r}, got {act_val!r}")
        if mismatches:
            fn.append(f"  occ {occ_num} (line {exp.get('line_start')}) — " + "; ".join(mismatches))
        else:
            tp.append(f"  occ {occ_num} (line {exp.get('line_start')})")

    for occ_num, act in sorted(actual_by_occ.items()):
        if occ_num not in expected_by_occ:
            fp.append(f"  occ {occ_num} (line {act.line_start}) — not in reference")

    score_value = len(tp) / max(len(expected), 1)

    lines = [
        f"Abbreviation: {abbr}",
        f"Number of occurrences: {len(expected)}",
        f"Abbreviation section: {'Yes' if abbr_section_def else 'No'}" + (f" — {abbr_section_def!r}" if abbr_section_def else ""),
        f"Definition at first use: {definition_at_first_use!r}" if definition_at_first_use else "Definition at first use: (none)",
        "",
        f"Correct (TP): {len(tp)}",
        *tp,
        f"Missed / wrong (FN): {len(fn)}",
        *fn,
        f"Extra (FP): {len(fp)}",
        *fp,
    ]
    return Score(value=score_value, explanation="\n".join(lines))


def _compare_abbreviation_list(
    output: AbbreviationCheckOutput, state: TaskState
) -> Score:
    """Deterministic match of the extracted abbreviations list against the target.

    Uses content-aware occurrence matching so that one prediction cannot satisfy
    two identical expected entries. Score = matched / total_expected.
    """
    expected_items: list[dict[str, Any]] = state.metadata.get(
        "target_abbreviations", []
    )
    if not expected_items:
        return Score(value=1.0, explanation="No target abbreviations defined")

    matched, errors, additional = _compare_abbreviation_occurrences(
        expected_items, output.abbreviations
    )
    total = len(expected_items)
    value = matched / total

    parts: list[str] = [f"Matched {matched}/{total}"]
    if errors:
        parts.append("Errors: " + "; ".join(e["type"] for e in errors))
    if additional:
        parts.append(f"Extra predictions: {len(additional)}")
    return Score(value=value, explanation=" | ".join(parts))
