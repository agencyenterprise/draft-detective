"""Deterministic checks of the sources a web-search workflow recommends.

Literature Review and Live Reports recommend sources found by live web search,
so no dataset can say which sources a correct run cites. What it can say is
what every recommended source must be: cited in full (a year and a DOI or URL,
so the reader can find it), dated on the right side of the document's
publication date (a literature review recommends only what the authors could
have cited; a live report only what came after), and, for a live report, not a
source the document already cites.

A citation is read from any line of the issue that carries a link: the skills
ask for the full citation with its DOI or URL, and a link-bearing line is how a
reference entry is told apart from prose that merely mentions a year. Its year
is the first year on the line (``(2018)``, ``(2022, June)``, ``2021.``), since
the year follows the authors and precedes the title, with the link removed
first so a DOI's digits are never read as one. Its first author is the surname
of the first name on the line, after any list marker and leading bold label
(``- **Recommended source (new; quality: high):**``): the last capitalised
word, not an initial, before the first comma, parenthesis, year or "and"
(``Stahlberg, F.``, ``Alan B. Krueger (1999)``, ``de Bruin, A.``,
``Iweala OI, et al.``). The same parse reads the
document's own reference list, the lines under a heading named References,
Bibliography or Works Cited.
"""

import json
import math
import re
from datetime import date
from typing import Optional, Sequence

from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState
from pydantic import BaseModel

from evals_inspectai.common.issue_checks import PER_KEY_METRICS, inventory_from_state, issues_from_state
from evals_inspectai.common.issue_inventory import ResolvedInventory
from evals_inspectai.common.simple_deep_agent_types import IssueItem

_LINK_RE = re.compile(r"https?://\S+|\bdoi:\s*\S+|\b10\.\d{4,9}/\S+", re.I)
_YEAR_RE = re.compile(r"(?<![\d./-])(1[5-9]\d{2}|20\d{2})(?!\d)")
# A list marker, then any leading bold or italic label (``**Source:**``, ``**Recommended
# source (new).**``) or plain label ending in a colon (``Source: ``).
_LEAD_RE = re.compile(
    r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?(?:(?:\*\*[^*]{1,120}\*\*|\*[^*]{1,120}\*|_[^_]{1,120}_)\s*[:.]?\s*|[A-Z][A-Za-z ]{1,30}:\s+)*"
)
_NAME_WORD_RE = re.compile(r"[^\W\d_][\w'’-]*")
# An initial or a run of initials, as in "Krueger, A. B." or "Iweala OI".
_INITIALS_RE = re.compile(r"^(?:[A-Z]\.?){1,3}$")
_REFERENCES_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(?:\d+\.?\s*)?(references|bibliography|works cited)\b", re.I)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s")


class Citation(BaseModel):
    text: str
    year: Optional[int]
    first_author: Optional[str]


def parse_citation(line: str) -> Citation:
    """The year and first author of one reference line (see the module docstring)."""
    text = line.strip()
    unlinked = _LINK_RE.sub(" ", text)
    match = _YEAR_RE.search(unlinked)
    return Citation(text=text, year=int(match.group(1)) if match else None, first_author=_first_author(unlinked))


def _first_author(line: str) -> Optional[str]:
    body = _LEAD_RE.sub("", line, count=1)
    # The first name ends at a comma, a parenthesis, the year, or the "and" / "&" before the next author.
    head = re.split(r"[,(&]|\sand\s|" + _YEAR_RE.pattern, body, maxsplit=1)[0]
    words = [w for w in _NAME_WORD_RE.findall(head) if w[0].isupper() and not _INITIALS_RE.match(w.rstrip("."))]
    # The surname is the last capitalised word that is not an initial: "Stahlberg, F.",
    # "Alan B. Krueger (1999)", "de Bruin, A.", "Iweala OI, et al.".
    return words[-1] if words else None


def issue_citations(issue: IssueItem) -> list[Citation]:
    """The reference entries an issue gives: every line of its description, long
    description or suggested action that carries a DOI or URL."""
    text = "\n".join(part for part in (issue.description, issue.long_description or "", issue.suggested_action or ""))
    return [parse_citation(line) for line in text.split("\n") if _LINK_RE.search(line)]


def document_references(document: str) -> list[Citation]:
    """The entries of the document's own reference list, one per non-blank line
    under a References, Bibliography or Works Cited heading, up to the next heading."""
    lines = document.split("\n")
    start = next((i for i, line in enumerate(lines) if _REFERENCES_HEADING_RE.match(line)), None)
    if start is None:
        return []
    entries: list[Citation] = []
    for line in lines[start + 1 :]:
        if _HEADING_RE.match(line):
            break
        if line.strip() and line.strip().lower().rstrip(".") != "none":
            entries.append(parse_citation(line))
    return entries


def _same_source(a: Citation, b: Citation) -> bool:
    return (
        a.year is not None
        and a.year == b.year
        and a.first_author is not None
        and b.first_author is not None
        and a.first_author.lower() == b.first_author.lower()
    )


def _named_own(issue: IssueItem, own: Sequence[Citation], linked: Sequence[Citation]) -> list[Citation]:
    """The document's own references the issue names by first author and year and does not
    already give as a linked citation: a recommendation to cite an existing reference in a
    new place, whose full citation is in the document and may have no link to give."""
    text = " ".join(part for part in (issue.title, issue.description, issue.long_description or ""))
    return [
        r
        for r in own
        if r.first_author
        and r.year
        and re.search(rf"\b{re.escape(r.first_author)}\b", text)
        and str(r.year) in text
        and not any(_same_source(r, c) for c in linked)
    ]


def _publication_year(inventory: ResolvedInventory) -> Optional[int]:
    return date.fromisoformat(inventory.publication_date).year if inventory.publication_date else None


def source_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory, report: str, after: bool, new_sources_only: bool
) -> tuple[dict[str, float], str]:
    """``cites_source``: share of reported issues giving at least one dated, linked citation.
    A literature review may also recommend one of the document's own references for a new
    place (see ``_named_own``): the named reference then counts as that issue's citation and
    goes through the date and report checks like any other. A live report (``new_sources_only``)
    gets no such exception, since it must recommend a source the document does not cite, and
    naming the document's own source there is usually a contrast with the newer one.
    ``sources_in_window``: share of dated citations published no later than the document's
    year (``after`` False, a literature review) or no earlier than it (``after`` True, a live
    report); a source from the publication year itself passes either way, since a year cannot
    say which side of the date it falls. NaN when the record has no publication date.
    ``not_already_cited`` (when ``new_sources_only``): share of citations whose first author and
    year match no entry of the document's reference list. ``report_lists_sources``: share of
    cited sources whose first author the report names, since the skills ask the report to list
    the full citation of every recommended source. Each is NaN with nothing to judge."""
    values: dict[str, float] = {"cites_source": math.nan, "sources_in_window": math.nan, "report_lists_sources": math.nan}
    if new_sources_only:
        values["not_already_cited"] = math.nan
    if not issues:
        return values, "nothing reported"
    notes: list[str] = []
    own = document_references(inventory.document)
    per_issue = [(issue, issue_citations(issue)) for issue in issues]
    if not new_sources_only:
        per_issue = [(issue, [*cites, *_named_own(issue, own, cites)]) for issue, cites in per_issue]
    uncited = [issue.title for issue, cites in per_issue if not any(c.year for c in cites)]
    values["cites_source"] = 1 - len(uncited) / len(issues)
    notes += [f"no dated, linked citation: {uncited}"] if uncited else []

    dated = [(c, c.year) for _, cites in per_issue for c in cites if c.year is not None]
    year = _publication_year(inventory)
    if year is not None and dated:
        outside = [c for c, published in dated if (published < year if after else published > year)]
        values["sources_in_window"] = 1 - len(outside) / len(dated)
        side = "before" if after else "after"
        notes += [f"{len(outside)} source(s) {side} {year}: " + "; ".join(c.text[:90] for c in outside)] if outside else []

    cited = [c for _, cites in per_issue for c in cites]
    authored = [c for c in cited if c.first_author]
    if authored:
        unlisted = sorted({c.first_author for c in authored if c.first_author and c.first_author not in report})
        values["report_lists_sources"] = 1 - sum(c.first_author in unlisted for c in authored) / len(authored)
        notes += [f"report does not name: {unlisted}"] if unlisted else []
    if new_sources_only and cited:
        repeated = [c for c in cited if any(_same_source(c, r) for r in own)]
        values["not_already_cited"] = 1 - len(repeated) / len(cited)
        notes += ["already in the document's references: " + "; ".join(c.text[:90] for c in repeated)] if repeated else []
    return values, " | ".join(notes) if notes else "every source cited in full and in its window"


def _report(state: TaskState) -> str:
    try:
        result = json.loads(state.output.completion).get("result") or {}
    except (ValueError, AttributeError):
        return ""
    return result.get("report_markdown") or ""


@scorer(metrics=PER_KEY_METRICS)
def source_checks(after: bool, new_sources_only: bool) -> Scorer:
    """``source_scores`` over a single-agent workflow's result: its issues and its report.
    ``after`` says which side of the publication date sources must fall on (see there)."""

    async def score(state: TaskState, target: Target) -> Score:
        issues, error = issues_from_state(state)
        values, explanation = source_scores(issues, inventory_from_state(state), _report(state), after, new_sources_only)
        if error:
            return Score(value={key: 0.0 for key in values}, explanation=error)
        return Score(value=values, explanation=explanation)

    return score


SOURCE_DESCRIPTIONS = {
    "report_lists_sources": "Share of recommended sources whose first author the report names: the report lists every recommended source. NaN when no source was cited.",
    "cites_source": "Share of reported issues giving at least one full citation (a line with a DOI or URL and a publication year); for a literature review, naming one of the document's own references by author and year also counts. NaN when nothing was reported.",
    "not_already_cited": "Share of recommended sources whose first author and year match no entry of the document's own reference list. NaN when no source was cited.",
}


def window_description(after: bool) -> str:
    side = "no earlier than" if after else "no later than"
    return (
        f"Share of dated recommended sources published {side} the document's publication year (the year itself passes). "
        "NaN when the record sets no publication date or no source is dated."
    )
