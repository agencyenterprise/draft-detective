"""Checks specific to the reviewer coverage report's verdict bookkeeping.

The coverage report is the one review-assistant output with an arithmetic core.
Its Part 1 carries a table counting every reviewer point across four verdict
categories, with the point IDs listed alongside each count, and Part 2 records a
verdict under each quoted point. That gives things a rule can check exactly,
without judging whether any individual verdict is *right*:

- the four categories are all present, including the ones that scored zero;
- the table accounts for every point exactly once and at one granularity,
  with each stated count matching the ids it lists;
- Part 2 actually uses the four-point scale, not only the table header;
- Part 1 states the recommendation the QAM needs.

Whether each verdict is correct is a judgement, and is graded by the rubric.
"""

import re

from evals_inspectai.common.html_report import (
    HtmlReport,
    PointId,
    expand_point_ids,
    find_point_ids,
    normalize,
    tables,
)

# The scale the skill defines. Order matters: the longer labels are matched
# first so "addressed" does not swallow "partially addressed".
VERDICTS = (
    "declined with rationale",
    "partially addressed",
    "not addressed",
    "addressed",
)

# The QAM's decision, in either direction. Deliberately does not match a bare
# "another pass": the skill requires a "What needs another pass" heading, so
# that phrasing is always present and matching it would make this vacuous.
_RECOMMENDATION = re.compile(
    # Either a sign-off, or a verb of returning followed within a few words by
    # what is being returned for. Reports phrase the second one freely:
    # "return for another pass", "return for a targeted second pass",
    # "returning the draft for one more focused pass", "send it back for
    # revision". The window is wide because the qualifiers stack up; it still
    # needs a verb of returning, which is what keeps the required heading
    # "What needs another pass" from matching on its own.
    r"sign[\s-]*off"
    r"|(?:return|returned|returns|returning|send|sends|sending|sent)\b"
    r"(?:\W+\w+){0,8}?\W+(?:pass|revision|round|rework)",
    re.IGNORECASE,
)

# The count a cell states, which precedes the ids it lists.
_LEADING_COUNT = re.compile(r"\s*(\d{1,3})")


def _verdict_of(cell: str) -> str | None:
    """Which verdict category a table cell names, if any."""
    text = normalize(cell)
    for verdict in VERDICTS:
        if verdict in text:
            return verdict
    return None


def _transpose(table: list[list[str]]) -> list[list[str]]:
    width = max(len(row) for row in table)
    padded = [row + [""] * (width - len(row)) for row in table]
    return [list(col) for col in zip(*padded)]


def _verdict_rows(table: list[list[str]]) -> dict[str, list[str]]:
    """The table's rows, keyed by the verdict category their first cell names."""
    return {
        verdict: row
        for row in table
        if row and (verdict := _verdict_of(row[0])) is not None
    }


# One <table> element. Used to locate the verdict table's own source so its
# text can be excluded from the report body; `tables()` returns parsed cells
# and cannot say where in the document they came from.
_TABLE_BLOCK = re.compile(r"<table\b[^>]*>.*?</table>", re.IGNORECASE | re.DOTALL)


def locate_verdict_table(
    report: HtmlReport,
) -> tuple[list[list[str]] | None, str]:
    """The summary table, oriented rows-per-category, and its HTML source.

    Chosen by content rather than position, since a report may carry other
    tables -- one run produced nine. Both orientations occur: usually the
    verdicts run down the first column, but some reports put the verdicts
    across the header and one row per reviewer. A transposed table is turned
    the right way up rather than rejected, which is what "no verdict table
    found" used to mean. Direct orientation wins over transposed across the
    whole document, so a later table is not preferred to an earlier one merely
    because it happens to parse in the usual direction.
    """
    parsed = [(block, tables(block)) for block in _TABLE_BLOCK.findall(report.html)]
    for block, candidates in parsed:
        for table in candidates:
            if len(_verdict_rows(table)) >= 3:
                return table, block
    for block, candidates in parsed:
        for table in candidates:
            if table and len(_verdict_rows(_transpose(table))) >= 3:
                return _transpose(table), block
    return None, ""


def _assigned_ids(rows: dict[str, list[str]]) -> dict[str, set[PointId]]:
    """The point ids the table assigns to each verdict, with ranges expanded.

    The whole row after the label is scanned rather than one column: a table
    that breaks counts down per reviewer puts the total in the last cell, and
    taking the union avoids depending on the layout.
    """
    return {
        verdict: set(expand_point_ids(" ".join(row[1:])))
        for verdict, row in rows.items()
    }


def _points_in_part2(report: HtmlReport, table_block: str) -> set[PointId]:
    """Point ids the report labels in Part 2, outside the summary table.

    Two things are excluded, for two reasons. The table's own ids, because
    counting them as evidence made the coverage rule circular: a row listing
    A1 and A2 satisfied itself even when only A1 was ever discussed. And
    Part 1, because a summary that recaps ids in prose is not the
    point-by-point assessment the table is supposed to index.
    """
    body = report.html.replace(table_block, " ", 1) if table_block else report.html
    return set(find_point_ids(HtmlReport(body).part2_raw))


def check_verdict_table(report: HtmlReport) -> tuple[bool, str]:
    """The table names all four categories and accounts for every point once.

    Once means in one category and at one granularity (a point is not counted
    alongside its own sub-points), every point labelled in Part 2 is counted
    and every counted point is labelled there, and each stated count matches
    the ids listed with it.

    The counts are not compared against a per-scenario expectation: which
    verdict a point deserves is a judgement the rubric grades. What is checked
    is that the bookkeeping holds together, which is what makes the table
    usable at all.
    """
    table, table_block = locate_verdict_table(report)
    if table is None:
        return False, "no verdict table found"

    rows = _verdict_rows(table)
    missing = [v for v in VERDICTS if v not in rows]
    if missing:
        return False, f"table omits {missing}"

    problems: list[str] = []

    assigned = _assigned_ids(rows)

    # A point belongs to exactly one category.
    seen: dict[PointId, str] = {}
    for verdict, ids in assigned.items():
        for point in sorted(ids):
            if point in seen and seen[point] != verdict:
                problems.append(
                    f"{point} counted under both {seen[point]} and {verdict}"
                )
            seen[point] = verdict

    # ...and at one granularity. Counting A3 and also counting A3.1 inflates
    # the total: a point and its split points are the same reviewer point
    # recorded twice, which the exact-id comparison above cannot see because
    # A3 and A3.1 are different strings. This holds whether or not the two
    # land in the same category.
    inflated = sorted(
        {p.split(".")[0] for p in seen if "." in p and p.split(".")[0] in seen}
    )
    if inflated:
        problems.append(
            f"{inflated} counted alongside their own sub-points, "
            "so the total counts them twice"
        )

    # The table indexes Part 2: every point assessed there is counted, and
    # every point counted is assessed there. The two directions get different
    # tolerance, deliberately. A parent id may excuse itself on the way in,
    # since Part 2 has to name A3 to introduce A3.1 and A3.2. It may not
    # excuse a count on the way out: a table counting A3.1 and A3.2 when
    # Part 2 only ever labels A3 has two rows a reader cannot trace to any
    # assessment, which is what the stable-id scheme exists to prevent.
    counted = set(seen)
    labelled = _points_in_part2(report, table_block)
    # A parent Part 2 names only to group its split points is not a missing
    # entry: when A3 becomes A3.1 to A3.3, the table counts the three and the
    # heading above them still reads A3.
    grouped = {PointId(point.split(".")[0]) for point in counted if "." in point}
    uncounted = sorted(labelled - counted - grouped)
    if uncounted:
        problems.append(
            f"{len(uncounted)} point(s) missing from the table: {uncounted[:6]}"
        )

    phantom = sorted(counted - labelled)
    if phantom:
        problems.append(
            f"{len(phantom)} point(s) counted but never labelled in Part 2: "
            f"{phantom[:6]}"
        )

    # The stated counts match the ids. Reports lay this out three ways: a cell
    # carrying both ("8, A1-A8" or "9 A1, A2, ..."), or a bare count cell with
    # the ids in a column of their own. Pairing within a cell whenever the cell
    # has both handles the first two and the per-reviewer breakdown, where a
    # bare "0" is one reviewer's count and not the row's total.
    for verdict, row in rows.items():
        cells = row[1:]
        paired: list[tuple[int, int, str]] = []
        bare: list[int] = []
        for cell in cells:
            match = _LEADING_COUNT.match(cell)
            if not match:
                continue
            listed = len(set(expand_point_ids(cell)))
            if listed:
                paired.append((int(match.group(1)), listed, cell))
            elif cell.strip().isdigit():
                bare.append(int(match.group(1)))

        if paired:
            for stated, listed, cell in paired:
                if stated != listed:
                    problems.append(
                        f"{verdict}: cell states {stated} but lists "
                        f"{listed} id(s) ({cell[:40]!r})"
                    )
            # A row that pairs counts with ids per reviewer usually carries a
            # bare total as well, and that total used to go unread: "2 A1,A2 |
            # 3 B1-B3 | 6" passed on five ids. Only an inflated total is
            # flagged. A bare cell smaller than the row's ids is indis-
            # tinguishable from one reviewer's share without reading the
            # header, and header wording varies too much to key on.
            if bare and max(bare) > len(assigned[verdict]):
                problems.append(
                    f"{verdict}: row totals {max(bare)} but lists "
                    f"{len(assigned[verdict])} id(s)"
                )
        elif bare and max(bare) != len(assigned[verdict]):
            problems.append(
                f"{verdict}: row states {max(bare)} but lists "
                f"{len(assigned[verdict])} id(s)"
            )

    summary = ", ".join(f"{v}={len(assigned[v])}" for v in VERDICTS)
    return (
        not problems,
        f"{summary}; {len(seen)} points counted"
        + ("; " + "; ".join(problems) if problems else ""),
    )


def check_verdict_vocabulary(report: HtmlReport) -> tuple[bool, str]:
    """Part 2 uses the four defined verdicts and does not invent others.

    A report that collapses the scale to addressed/not addressed loses the
    distinction the skill exists to preserve: a decline with a stated reason is
    settled, and only `not addressed` should read as a gap.

    The summary table's own labels are discounted first. `locate_verdict_table`
    only recognises a table when at least three of its rows name a verdict, so
    counting across the whole report meant any report with a usable table
    cleared the bar automatically and this check could never fail.

    The bar is then set by the report's own arithmetic: every category the
    table assigns a point to has to be used in Part 2 as well. Asking instead
    for a fixed non-binary verdict would be wrong, because whether a scenario
    contains anything partial or declined is a property of the memo, not of
    the report -- the organics scenario is nine corrections made and one
    concern ignored, and an addressed/not-addressed Part 2 is the honest
    answer there. Deriving the requirement from the table catches the failure
    that is really in scope, a scale declared in a header and then abandoned,
    without asking any report to invent a verdict its scenario never earned.
    """
    table, table_block = locate_verdict_table(report)
    rows = _verdict_rows(table) if table else {}

    # Part 2 with the table cut out of the document first, rather than its
    # counts subtracted afterwards: the table normally sits in Part 1, so
    # subtracting it from a Part 2 tally would deduct labels that were never
    # in the tally to begin with. Part 1 is excluded because its prose recap
    # would otherwise stand in for the assessments -- a summary reading "two
    # points were partially addressed" satisfied this check while Part 2
    # labelled everything "resolved".
    body = report.html.replace(table_block, " ", 1) if table_block else report.html
    scope = HtmlReport(body).part2
    counts = {v: scope.count(v) for v in VERDICTS}
    # "addressed" is a substring of "partially addressed" and "not addressed",
    # so those two are discounted. "declined with rationale" is not -- it does
    # not contain the substring, and subtracting it (as this did) deflated the
    # addressed tally by one per decline for no reason.
    counts["addressed"] -= counts["partially addressed"] + counts["not addressed"]
    used = {v for v, n in counts.items() if n > 0}
    detail = ", ".join(f"{v}={max(counts[v], 0)}" for v in VERDICTS)

    if len(used) < 2:
        return (
            False,
            f"Part 2 barely uses the verdict scale: {detail}",
        )

    claimed = {v for v, ids in _assigned_ids(rows).items() if ids}
    abandoned = sorted(claimed - used)
    if abandoned:
        return (
            False,
            f"the table assigns points to {abandoned} but Part 2 never uses "
            f"{'that verdict' if len(abandoned) == 1 else 'those verdicts'}: "
            f"{detail}",
        )
    return True, f"in Part 2: {detail}"


def check_recommendation(report: HtmlReport) -> tuple[bool, str]:
    """Part 1 states the QAM's decision explicitly.

    The report exists to answer one question: sign off, or send the revision
    back. Leaving the reader to infer it from the counts fails the output's
    stated purpose.
    """
    head = report.text[: int(0.4 * len(report.text))] or report.text
    match = _RECOMMENDATION.search(head)
    if not match:
        return False, "no explicit sign-off or return-for-another-pass recommendation"
    return True, f"recommendation stated ({match.group(0)!r})"
