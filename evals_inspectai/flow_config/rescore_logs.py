"""Rescore all .eval logs in this directory using single_entry_scorer.

Usage:
    python evals_inspectai/flow_config/rescore_logs.py [logs_dir]

Rewrites each .eval file in place with updated scores and explanations.

The target for each sample is resolved in priority order:
  1. sample.target (set by the entries task — JSON list from the dataset)
  2. Current references.json on disk, keyed by metadata["reference_file"] +
     metadata["filename"] + metadata["abbr"]  (variants task logs)
  3. metadata["target_abbreviations"] (older variants logs without reference_file)
"""

import asyncio
import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.scorer import Target

from evals_inspectai.e2e.abbreviation_checker.abbreviation_checker_e2e import (
    single_entry_scorer,
)

# Cache loaded reference files so we don't re-read them per sample.
_ref_cache: dict[str, dict] = {}


def _target_from_reference(metadata: dict) -> str | None:
    """Build a JSON target from the current references.json on disk."""
    ref_file = metadata.get("reference_file")
    filename = metadata.get("filename")
    abbr = metadata.get("abbr")
    if not (ref_file and filename and abbr):
        return None
    if ref_file not in _ref_cache:
        path = Path(ref_file)
        if not path.is_file():
            return None
        _ref_cache[ref_file] = json.loads(path.read_text(encoding="utf-8"))
    refs = _ref_cache[ref_file]
    entries = [
        e for e in refs.get(filename, {}).get("abbreviations", [])
        if e["abbr"] == abbr and not e.get("ignored", False)
    ]
    return json.dumps(entries) if entries else None


def _resolve_target(sample) -> str:  # type: ignore[no-untyped-def]
    """Return the best available target text for this sample."""
    # 1. entries-task logs carry the target in sample.target
    if sample.target:
        return sample.target
    # 2. variants-task logs: re-read from the current reference file on disk
    ref_target = _target_from_reference(sample.metadata or {})
    if ref_target:
        return ref_target
    # 3. Fall back to whatever was stored in metadata at eval-run time
    entries = (sample.metadata or {}).get("target_abbreviations", [])
    return json.dumps(entries)


async def rescore_log(path: Path, scorer_fn: object) -> int:
    log = read_eval_log(str(path))
    if not log.samples:
        print(f"  skip {path.name} (no samples)")
        return 0

    for sample in log.samples:
        target_text = _resolve_target(sample)
        score = await scorer_fn(sample, Target(target_text))  # type: ignore[operator]
        updated = {k: v for k, v in (sample.scores or {}).items() if k != "structured_output_scorer"}
        updated["single_entry_scorer"] = score
        sample.scores = updated

    write_eval_log(log, str(path))
    return len(log.samples)


async def main() -> None:
    logs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "logs"
    eval_files = sorted(logs_dir.glob("*.eval"))
    if not eval_files:
        print(f"No .eval files found in {logs_dir}")
        return

    scorer_fn = single_entry_scorer()
    total = 0
    for i, path in enumerate(eval_files, 1):
        print(f"[{i}/{len(eval_files)}] {path.name}")
        count = await rescore_log(path, scorer_fn)
        total += count
        print(f"  rescored {count} sample(s)")

    print(f"\nDone. {total} samples rescored across {len(eval_files)} log(s).")


if __name__ == "__main__":
    asyncio.run(main())
