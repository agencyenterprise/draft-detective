"""Summarise abbreviation-checker errors across one or more Inspect eval logs.

Reads the hierarchical ``metadata`` the ``abbreviation_list`` scorer writes and
turns it into a categorised, aggregated error report so you can see *what kind*
of mistakes recur without opening each log by hand.

Usage:
    # Latest log in ./logs
    uv run python evals_inspectai/e2e/abbreviation_checker/analyze_logs.py

    # A specific log (or several)
    uv run python evals_inspectai/e2e/abbreviation_checker/analyze_logs.py logs/<name>.eval

    # Every log for this task in ./logs
    uv run python evals_inspectai/e2e/abbreviation_checker/analyze_logs.py --all
"""

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

_TASK = "abbreviation-checker-from-files"
_SCORER = "abbreviation_list"


def _log_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "logs"


def _resolve_logs(paths: list[str], use_all: bool) -> list[str]:
    if paths:
        return paths
    logs = [
        log.name
        for log in list_eval_logs(str(_log_dir()))
        if _TASK in Path(log.name).name
    ]
    if not logs:
        raise SystemExit(f"No '{_TASK}' logs found in {_log_dir()}")
    return sorted(logs) if use_all else [sorted(logs)[-1]]


def _iter_sample_metadata(log: EvalLog) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for sample in log.samples or []:
        score = (sample.scores or {}).get(_SCORER)
        if score and score.metadata:
            out.append((str(sample.id), score.metadata))
    return out


def _print_sample_report(sample_id: str, meta: dict[str, Any]) -> None:
    summary = meta.get("summary", {})
    print(f"\n  {sample_id}")
    print(
        f"    score {summary.get('score')} | "
        f"matched {summary.get('matched')}/{summary.get('total')} | "
        f"missing {summary.get('missing')} | "
        f"mismatched {summary.get('mismatched')} | "
        f"extra {summary.get('extra')}"
    )
    by_field = meta.get("by_field", {})
    if by_field:
        print("    field mismatches (where diffs cluster):")
        for field, count in by_field.items():
            print(f"      - {field}: {count}")


def _aggregate(all_meta: list[dict[str, Any]]) -> None:
    field_totals: Counter[str] = Counter()
    missing_totals: Counter[str] = Counter()
    diff_shapes: Counter[str] = Counter()

    for meta in all_meta:
        for field, count in meta.get("by_field", {}).items():
            field_totals[field] += count
        for key in meta.get("missing", []):
            missing_totals[key] += 1
        for mm in meta.get("mismatches", []):
            for field, (expected, actual) in mm.get("diffs", {}).items():
                # A "shape" collapses many entries with the same expected→actual
                # transition into one line, e.g. the systematic
                # 'artificial intelligence'→None backfill regression.
                diff_shapes[f"{field}: {expected!r} -> {actual!r}"] += 1

    print("\n=== AGGREGATE ACROSS LOGS ===")
    print(f"\nMismatches by field ({len(all_meta)} sample(s)):")
    for field, count in field_totals.most_common():
        print(f"  {count:>5}  {field}")

    print("\nMost common expected->actual transitions:")
    for shape, count in diff_shapes.most_common(15):
        print(f"  {count:>5}  {shape}")

    print("\nMost frequently missing reference entries:")
    for key, count in missing_totals.most_common(15):
        print(f"  {count:>5}  {key}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", help="Log file path(s). Default: latest.")
    parser.add_argument(
        "--all", action="store_true", help="Analyse every task log in ./logs."
    )
    args = parser.parse_args()

    log_names = _resolve_logs(args.logs, args.all)
    all_meta: list[dict[str, Any]] = []

    for name in log_names:
        log = read_eval_log(name)
        print(f"\n### {Path(name).name}")
        samples = _iter_sample_metadata(log)
        if not samples:
            print(
                "  (no abbreviation_list metadata; this utility does not analyze "
                "single_entry_scorer logs)"
            )
            continue
        for sample_id, meta in samples:
            _print_sample_report(sample_id, meta)
            all_meta.append(meta)

    if all_meta:
        _aggregate(all_meta)


if __name__ == "__main__":
    main()
