"""The deterministic rules, and the detail behind each verdict.

Seven checks on the shape of the delivery and four against the dataset's
ground-truth inventory. Each returns `(value, detail)`; the scorer turns them
into one metric per rule so a regression names itself.

Shape, none of which says whether a classification is *right*: `report` (a
substantive markdown report), `inventory_table` (the report's inventory table,
found by the reproducibility column its header names rather than by being the
widest table, has at least a row per reported result), `result_count` (at least as many results as the dataset
requires), `labels` (a recognised reproducibility label in every issue title),
`severity_split` (reproducible is `none`, only not-reproducible carries a real
severity), `line_ranges` (inside the document) and `no_duplicates` (no issue
title repeated).

Ground truth: `completeness` (share of required expected results found),
`class_accuracy` (share of found results given the right class), `no_extras`
(share of reported results that are in the expected inventory) and
`severity_ordering` (among found not-reproducible results, one the document
rests on more is never given a lower severity; only the ordering is asserted,
not the level).
"""

from typing import Any

from evals_inspectai.common.simple_deep_agent_types import AgentCheckResult, IssueItem
from evals_inspectai.e2e.results_extraction.contract import (
    CLASS_LABELS,
    IMPORTANCE_RANK,
    MIN_REPORT_CHARS,
    NOT_REPRODUCIBLE,
    REAL_SEVERITIES,
    SEVERITY_RANK,
    severity_matches_label,
)
from evals_inspectai.e2e.results_extraction.matching import match_expected
from evals_inspectai.e2e.results_extraction.parsing import label_of, table_row_count

def _ground_truth_checks(
    issues: list[IssueItem],
    expected: list[dict[str, Any]],
    labels: list[str | None],
    expects_none: bool = False,
) -> dict[str, tuple[bool | float, str]]:
    """Compare the reported inventory against the dataset's expected one."""
    if expects_none:
        # The whole assertion is that nothing should be reported, so an empty
        # inventory passes all four and anything reported fails them.
        verdict = float(not issues)
        note = (
            "document presents no results and none were reported"
            if not issues
            else f"document presents no results, but {len(issues)} were reported"
        )
        return {
            key: (verdict, note)
            for key in ("completeness", "class_accuracy", "no_extras", "severity_ordering")
        }
    if not expected:
        # Every record is required to declare its inventory (`_load_dataset`
        # enforces it), so reaching here means the dataset is malformed. Failing
        # is the honest reading: scoring 1.0 would report four passes that were
        # never tested, and a sample with no ground truth cannot be checked.
        note = "no expected inventory declared -- this sample cannot be scored"
        return {
            key: (0.0, note)
            for key in ("completeness", "class_accuracy", "no_extras", "severity_ordering")
        }

    matched = match_expected(issues, expected)
    by_id = {entry["id"]: entry for entry in expected}

    required = [e["id"] for e in expected if e.get("required", True)]
    found = [entry_id for entry_id in required if entry_id in matched]
    missing = [entry_id for entry_id in required if entry_id not in matched]
    completeness = (
        len(found) / len(required) if required else 1.0,
        (
            f"{len(found)}/{len(required)} required result(s) found"
            + (f"; missing {', '.join(missing)}" if missing else "")
        )
        if required
        else "no required results declared",
    )

    wrong_class = []
    correct = 0
    for entry_id, i_index in matched.items():
        want = CLASS_LABELS[by_id[entry_id]["class"]]
        got = labels[i_index]
        if got == want:
            correct += 1
        else:
            wrong_class.append(f"{entry_id}: {got or 'unlabelled'}, expected {want}")
    class_accuracy = (
        correct / len(matched) if matched else 0.0,
        (
            f"{correct}/{len(matched)} classified correctly"
            + (f"; {'; '.join(wrong_class)}" if wrong_class else "")
        )
        if matched
        else "no expected result was found, so nothing to classify",
    )

    # Fractional, not binary: one defensible extra reading and a run that
    # invented five results used to score the same zero, which made the metric
    # unusable for telling those apart.
    extras = [
        issues[i].title for i in range(len(issues)) if i not in set(matched.values())
    ]
    accounted = len(issues) - len(extras)
    no_extras = (
        accounted / len(issues) if issues else 0.0,
        (
            "no results reported"
            if not issues
            else (
                f"all {len(issues)} reported result(s) are in the expected inventory"
                if not extras
                else f"{len(extras)}/{len(issues)} unexpected: "
                + "; ".join(repr(e) for e in extras)
            )
        ),
    )

    # Severity ordering, over the non-reproducible results that were both found
    # and labelled as such: a result the document leans on harder must not carry
    # a lower severity than one it leans on less.
    ranked: list[tuple[int, int, str]] = []
    for entry_id, i_index in matched.items():
        entry = by_id[entry_id]
        if entry["class"] != "not_reproducible" or labels[i_index] != NOT_REPRODUCIBLE:
            continue
        ranked.append(
            (
                IMPORTANCE_RANK[entry["importance"]],
                SEVERITY_RANK.get(issues[i_index].severity, 0),
                entry_id,
            )
        )

    inversions = [
        f"{a_id} ({'>' if a_imp > b_imp else '<'} importance) is severity-ranked "
        f"{'below' if a_sev < b_sev else 'above'} {b_id}"
        for a_imp, a_sev, a_id in ranked
        for b_imp, b_sev, b_id in ranked
        if a_imp > b_imp and a_sev < b_sev
    ]
    comparable = any(
        a_imp != b_imp for a_imp, _, _ in ranked for b_imp, _, _ in ranked
    )
    severity_ordering = (
        not inversions,
        (
            "no non-reproducible results of differing importance to compare"
            if not comparable
            else (
                f"{len(ranked)} non-reproducible result(s) ordered correctly"
                if not inversions
                else "; ".join(inversions)
            )
        ),
    )

    return {
        "completeness": completeness,
        "class_accuracy": class_accuracy,
        "no_extras": no_extras,
        "severity_ordering": severity_ordering,
    }


def inventory_check_results(
    result: AgentCheckResult, meta: dict[str, Any], document_lines: int
) -> dict[str, tuple[bool | float, str]]:
    """Run every deterministic rule, each with the detail behind its verdict."""
    expected: list[dict[str, Any]] = meta.get("expected_results") or []
    expected_min = sum(1 for e in expected if e.get("required", True))
    # A document that presents no results at all inverts most of these: the
    # correct output is an empty issue list, so "no results reported" is the pass
    # rather than the vacuous case.
    expects_none: bool = bool(meta.get("expects_no_results"))
    issues = result.issues
    report = (result.report_markdown or "").strip()
    labels = [label_of(issue) for issue in issues]
    labelled = [(issue, label) for issue, label in zip(issues, labels) if label]

    checks: dict[str, tuple[bool | float, str]] = {}

    checks["report"] = (
        len(report) >= MIN_REPORT_CHARS,
        f"{len(report)} chars (min {MIN_REPORT_CHARS})",
    )

    # The skill's report format: a table of every result. Fewer rows than
    # results means the report and the issue list disagree about the inventory.
    rows, table_kind = table_row_count(report)
    checks["inventory_table"] = (
        (not issues) if expects_none else (bool(issues) and rows >= len(issues)),
        f"{rows} row(s) in the {table_kind} for {len(issues)} result(s)",
    )

    checks["result_count"] = (
        len(issues) >= expected_min,
        f"{len(issues)} result(s), expected at least {expected_min}",
    )

    # Every title has to carry one of the four labels, which is what makes the
    # class visible in the issue list and checkable here.
    unlabelled = [issue.title for issue, label in zip(issues, labels) if not label]
    checks["labels"] = (
        (not issues) if expects_none else (bool(issues) and not unlabelled),
        (
            "no results reported"
            if not issues
            else (
                "every title carries a label"
                if not unlabelled
                else f"{len(unlabelled)} unlabelled, e.g. {unlabelled[0]!r}"
            )
        ),
    )

    # Reproducible -> `none`, not reproducible -> a real severity. Judged over
    # the labelled results only: an unlabelled one is the `labels` check's
    # business, and failing it twice would hide how many rules actually broke.
    wrong = [
        f"{issue.title!r} is {issue.severity}"
        for issue, label in labelled
        if label and not severity_matches_label(issue.severity, label)
    ]
    checks["severity_split"] = (
        (not issues) if expects_none else (bool(labelled) and not wrong),
        (
            "no labelled results to check"
            if not labelled
            else (
                f"{len(labelled)} result(s) split correctly"
                if not wrong
                else "; ".join(wrong)
            )
        ),
    )

    # Ordered and positive is not enough: lines 900-905 of a 100-line document
    # are as unusable as a reversed range, and the reporting tool does not check
    # the upper bound either.
    bad_ranges = [
        f"{issue.title!r} lines {issue.start_line}-{issue.end_line}"
        for issue in issues
        if issue.start_line < 1
        or issue.end_line < issue.start_line
        or issue.end_line > document_lines
    ]
    checks["line_ranges"] = (
        (not issues) if expects_none else (bool(issues) and not bad_ranges),
        (
            "no results reported"
            if not issues
            else (
                f"all line ranges land inside the document's {document_lines} lines"
                if not bad_ranges
                else f"document has {document_lines} lines; " + "; ".join(bad_ranges)
            )
        ),
    )

    # A result reported twice is one result, and duplicate titles have shown up
    # in real runs (one emitted eighteen issues with three copies of one result).
    seen: dict[str, int] = {}
    for issue in issues:
        key = issue.title.strip().lower()
        seen[key] = seen.get(key, 0) + 1
    duplicates = {title: n for title, n in seen.items() if n > 1}
    checks["no_duplicates"] = (
        not duplicates,
        "no repeated issue titles"
        if not duplicates
        else "; ".join(f"{title!r} reported {n} times" for title, n in duplicates.items()),
    )

    checks.update(_ground_truth_checks(issues, expected, labels, expects_none))
    return checks

