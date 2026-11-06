"""Generate the results table in `docs/eval-scores.md` from the recorded logs.

Every row is computed from the `.eval` log it links to in `docs/evals/`, so the
table never drifts from the logs. Recording a new run copies its log there,
points the eval's row at it and deletes the log it replaces:

    uv run python -m evals_inspectai.scores_table --record <path/to/run.eval> ...
    uv run python -m evals_inspectai.scores_table            # regenerate only
    uv run python -m evals_inspectai.scores_table --check    # fail if stale

The rules for a row:

- **Scorers** counts each metric a scorer reports, by kind: *judged* when the
  scorer's name contains "judge" or "rubric", *identification* for
  `input_identification`, *deterministic* otherwise. A metric no sample
  produced (NaN, e.g. a decoy kind absent from the dataset) is left out.
- **Overall avg** is the unweighted mean of those metrics.
- **Date** is the day the run was created.

Rows are added by hand (number and eval name); the script fills in the rest.
The `#` and eval columns and the prose are untouched.
"""

import argparse
import math
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from inspect_ai.log import read_eval_log
from pydantic import BaseModel

DOC = Path("docs/eval-scores.md")
LOG_DIR = Path("docs/evals")
VIEWER = "https://agencyenterprise.github.io/draft-detective/evals-viewer/#/tasks/"
KINDS = ("deterministic", "judged", "identification")

ROW = re.compile(
    r"^\| (?P<num>\d+) \| `(?P<name>\w+)`(?P<note>\[\^\w+\])? \|.*?#/tasks/(?P<log>[^)]+\.eval)\) \|$"
)
MEAN_ROW = re.compile(r"^\| \| \*\*Mean across all evals\*\* \|.*$")
TOTAL_LINE = re.compile(r"^- \*\*Total:\*\* .*$")
UPDATED_LINE = re.compile(r"^- \*\*Last updated:\*\* .*$")


class RunSummary(BaseModel):
    """What one recorded run contributes to its row."""

    task: str
    samples: int
    epochs: int
    scorers: str
    overall: float
    created: str


def metric_kind(scorer: str) -> str:
    """The kind a scorer's metrics are counted under."""
    name = scorer.lower()
    if "identification" in name:
        return "identification"
    if "judge" in name or "rubric" in name:
        return "judged"
    return "deterministic"


def describe(kind: str, values: list[float]) -> str:
    """One kind's part of the Scorers column, e.g. `20 deterministic 0.955–1.000`."""
    low, high = f"{min(values):.3f}", f"{max(values):.3f}"
    if len(values) == 1:
        spread = low
    elif low == high:
        spread = f"all {low}"
    else:
        spread = f"{low}–{high}"
    return f"{len(values)} {kind} {spread}"


def summarize(log: Path) -> RunSummary:
    """Summarize a recorded run by the rules in the module docstring."""
    header = read_eval_log(str(log), header_only=True)
    if header.results is None:
        raise ValueError(f"{log} has no results; was the run finished?")
    by_kind: dict[str, list[float]] = {kind: [] for kind in KINDS}
    for score in header.results.scores:
        metric = score.metrics.get("mean") or score.metrics.get("applicable_mean")
        if metric is None or math.isnan(metric.value):
            continue
        by_kind[metric_kind(score.scorer)].append(metric.value)
    values = [v for kind in KINDS for v in by_kind[kind]]
    return RunSummary(
        task=header.eval.task.removesuffix("_e2e"),
        samples=header.eval.dataset.samples or 0,
        epochs=header.eval.config.epochs or 1,
        scorers=" · ".join(describe(k, by_kind[k]) for k in KINDS if by_kind[k]),
        overall=sum(values) / len(values),
        created=header.eval.created[:10],
    )


def row_text(num: str, name: str, note: str, log: str, run: RunSummary) -> str:
    """The table row for one eval."""
    run_id = log.removesuffix(".eval").rsplit("_", 1)[-1]
    link = f"[`…_{run_id}.eval`]({VIEWER}{log})"
    return (
        f"| {num} | `{name}`{note} | {run.samples} | {run.epochs} | {run.scorers} "
        f"| **{run.overall:.3f}** | {run.created} | {link} |"
    )


class Recording(BaseModel):
    """New runs to record: the table pointing at them, and what they replace."""

    lines: list[str]
    sources: dict[str, Path]
    replaced: list[str]


def _row_index(lines: list[str], task: str) -> int:
    for index, line in enumerate(lines):
        if (match := ROW.match(line)) and match["name"] == task:
            return index
    raise SystemExit(f"No row for `{task}` in {DOC}: add it by hand first.")


def plan_recording(logs: list[Path], lines: list[str]) -> Recording:
    """Point each new log's row at it, touching no file yet.

    Every log is read and matched to its row before anything is copied or
    deleted, so a bad log on the command line leaves the report as it was.
    """
    lines = list(lines)
    sources: dict[str, Path] = {}
    replaced: list[str] = []
    for log in logs:
        index = _row_index(lines, summarize(log).task)
        old = ROW.match(lines[index])["log"]  # type: ignore[index]  # matched in _row_index
        if old in sources:
            raise SystemExit(f"Two logs given for the row of {log.name}.")
        lines[index] = lines[index].replace(old, log.name)
        sources[log.name] = log
        if old != log.name:
            replaced.append(old)
    return Recording(lines=lines, sources=sources, replaced=replaced)


def regenerate(lines: list[str], sources: dict[str, Path] | None = None) -> list[str]:
    """Rewrite every row, the mean row and the header totals from the logs.

    A row's log is read from `docs/evals/`, or from `sources` when it is a new
    run not copied there yet.
    """
    sources = sources or {}
    runs: list[RunSummary] = []
    out: list[str] = []
    for line in lines:
        if m := ROW.match(line):
            run = summarize(sources.get(m["log"], LOG_DIR / m["log"]))
            runs.append(run)
            line = row_text(m["num"], m["name"], m["note"] or "", m["log"], run)
        elif MEAN_ROW.match(line) and runs:
            mean = sum(r.overall for r in runs) / len(runs)
            line = f"| | **Mean across all evals** | | | | **{mean:.3f}** | | |"
        out.append(line)
    return [totals(line, runs) for line in out]


def totals(line: str, runs: list[RunSummary]) -> str:
    """The header's Total and Last updated lines, from the runs in the table."""
    if TOTAL_LINE.match(line):
        epochs = sorted({r.epochs for r in runs})
        at = (
            f"epochs={epochs[0]}"
            if len(epochs) == 1
            else "epochs " + "/".join(map(str, epochs))
        )
        samples = sum(r.samples for r in runs)
        return (
            f"- **Total:** {len(runs)} evals · {samples} runnable samples · run at {at}"
        )
    if UPDATED_LINE.match(line):
        return f"- **Last updated:** {max(r.created for r in runs)}"
    return line


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", nargs="+", type=Path, default=[], metavar="LOG")
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the table is stale"
    )
    args = parser.parse_args()
    if args.check and args.record:
        parser.error("--check reads the table as it is; it cannot take --record")
    current = DOC.read_text().splitlines()
    if args.check:
        if regenerate(current) != current:
            sys.exit(
                f"{DOC} is stale: run `uv run python -m evals_inspectai.scores_table`."
            )
        return
    recording = plan_recording(args.record, current)
    updated = regenerate(recording.lines, recording.sources)
    # Only now, with every log read and the table computed, touch the files:
    # copy the new logs in, write the table, then drop the logs it no longer
    # links to.
    for name, source in recording.sources.items():
        if source.resolve() != (LOG_DIR / name).resolve():
            shutil.copy2(source, LOG_DIR / name)
    DOC.write_text("\n".join(updated) + "\n")
    for name in recording.replaced:
        (LOG_DIR / name).unlink(missing_ok=True)
    print(f"Updated {DOC} ({date.today()}).")


if __name__ == "__main__":
    main()
