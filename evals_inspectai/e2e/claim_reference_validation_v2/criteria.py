"""What Claim Reference Validation is judged on, beyond the generic layers.

The workflow keeps one record per validated citation in its state
(``citation_issues``), each with the evidence-alignment level it assigned, and
the manifest turns each into one issue, titled after the level. The eval reads
the records and takes the level itself as the issue title (``as_issues``):
"Supported Citation" would match inside "Partially Supported Citation" under
whole-word title matching, while ``supported`` and ``partially_supported`` are
distinct words. ``title_correct`` is then the share of detected citations given
the right level.

Beyond that single accuracy, what the check gets right or wrong is where it
errs, which the skill says is at the boundaries between adjacent levels:
``label_<level>`` breaks accuracy down by the level a correct run assigns, so a
run that hedges supported citations down to partial support shows in
``label_supported`` rather than disappearing into the mean. Every evidence quote
the run cites must come verbatim from a supporting file (``evidence_verbatim``),
since a quote that is not in the source is invented evidence, and the cited
text each record quotes must come verbatim from the document
(``cited_text_verbatim``), since the author finds the citation by it. Two graded
criteria read each detected citation against the labeller's account of what the
source says: the rationale says what the source actually backs or fails to
back, and, for a citation that is not supported, the suggested action tells the
author what to change, with any corrected figure or scope checked against that
account.
"""

import math
import re
from typing import Any, Mapping, Sequence

from evals_inspectai.common.issue_checks import hit_pairs
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue, quoted_verbatim
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

LEVELS = ("supported", "partially_supported", "unsupported", "unverifiable")
# The severity the manifest gives each level's issue.
SEVERITIES = {"supported": "none", "partially_supported": "medium", "unsupported": "high", "unverifiable": "medium"}


def _level(record: Mapping[str, Any]) -> str:
    value = record.get("evidence_alignment")
    if isinstance(value, dict):  # an enum serialised with its value
        value = value.get("value")
    return str(value or "")


def as_issues(citation_issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The workflow's citation records as issues the generic checks read: the level as
    the title, the rationale as the description, the cited text as the long description
    (what the issue quotes), the feedback as the suggested action."""
    return [
        {
            "title": _level(r),
            "description": r.get("rationale") or "",
            "long_description": r.get("quoted_text") or "",
            "suggested_action": r.get("feedback") or None,
            "severity": SEVERITIES.get(_level(r), "medium"),
            "start_line": r.get("line_start") or 0,
            "end_line": r.get("line_end") or 0,
        }
        for r in citation_issues
    ]


def label_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``label_<level>``: of the detected citations a correct run gives that level, the
    share the run gave it; NaN when the sample has none detected."""
    by_level: dict[str, list[float]] = {level: [] for level in LEVELS}
    notes = []
    for expected, issue in hit_pairs(issues, inventory)[1]:
        if expected.title not in by_level:
            continue
        right = issue.title == expected.title
        by_level[expected.title].append(float(right))
        if not right:
            notes.append(f"{expected.id}: {issue.title or 'no level'}, expected {expected.title}")
    values = {f"label_{level}": (sum(v) / len(v) if v else math.nan) for level, v in by_level.items()}
    return values, " | ".join(notes) if notes else "every detected citation got its level"


_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s.*$", re.M)


def evidence_scores(
    citation_issues: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, str]]
) -> tuple[dict[str, float], str]:
    """``evidence_verbatim``: share of the evidence quotes the run cites that occur verbatim
    in a supporting file; NaN when it cites none. The files' headings are left out, so a
    quote running from one paragraph into the next under a new heading still counts."""
    quotes = [
        s["quote"]
        for r in citation_issues
        for s in r.get("evidence_sources") or []
        if isinstance(s, dict) and (s.get("quote") or "").strip()
    ]
    if not quotes:
        return {"evidence_verbatim": math.nan}, "no evidence quoted"
    texts = [_HEADING_LINE_RE.sub("", s["markdown"]) for s in sources]
    invented = [q for q in quotes if not any(quoted_verbatim(q, t) for t in texts)]
    value = 1 - len(invented) / len(quotes)
    return {"evidence_verbatim": value}, (f"quotes not in any source: {invented}" if invented else "every quote is in a source")


def quote_scores(citation_issues: Sequence[Mapping[str, Any]], document: str) -> tuple[dict[str, float], str]:
    """``cited_text_verbatim``: share of the citation records whose cited text occurs
    verbatim in the document; NaN when there are none."""
    if not citation_issues:
        return {"cited_text_verbatim": math.nan}, "no citation reported"
    missing = [r.get("quoted_text") or "" for r in citation_issues if not quoted_verbatim(r.get("quoted_text") or "", document)]
    value = 1 - len(missing) / len(citation_issues)
    return {"cited_text_verbatim": value}, (f"cited text not in the document: {missing}" if missing else "every cited text is in the document")


RATIONALE_CRITERION = (
    "The reviewer checked whether a cited source supports a claim in a research document, and the labeller has "
    "described what the source actually says about it. Grade whether the reviewer's analysis gives the right "
    "reason: it says what the source backs and what it does not back in a way consistent with the labeller "
    "(the figure it reports, the narrower scope it covers, the opposite finding, the silence on the claim's point, "
    "or that the source was not available). Ignore the level the reviewer assigned; grade the reason. It is "
    "incorrect if it attributes to the source something the labeller says it does not say, or misses the "
    "element the labeller names as unbacked. It is partially correct if the reason is right but vague."
)

ACTION_CRITERION = (
    "The reviewer found that a cited source does not fully support a claim in a research document (the claim "
    "overreaches the source, contradicts it, is not in it, or the source was not available), the passage the "
    "claim sits in is shown, and the labeller has described what the source actually says. Grade whether the "
    "suggested action tells the author concretely what to change: narrow the claim to what the source covers "
    "(naming the scope), correct the figure or direction to the source's, cite a source that does back the claim "
    "or remove it, or supply the missing source. A correction that states a figure, scope or finding the "
    "labeller's account contradicts, or one the source does not contain, is incorrect. Advice that fits any "
    "citation (\"verify the citation\", \"ensure claims are supported\") is incorrect."
)


def _not_supported(expected: ResolvedIssue) -> bool:
    return expected.title != "supported"


JUDGE_CRITERIA = [
    JudgeCriterion(key="rationale_matches_source", criterion=RATIONALE_CRITERION, scope="expected", passage="section", reads="analysis", reference=True),
    JudgeCriterion(
        key="action_fixes_citation",
        criterion=ACTION_CRITERION,
        scope="expected",
        passage="section",
        reference=True,
        applies_to=_not_supported,
    ),
]

JUDGE_DESCRIPTIONS = {
    "rationale_matches_source": "Graded per detected citation against the labeller's account of the source: the reported rationale says what the source backs and does not back (C=1, P=0.5, I=0).",
    "action_fixes_citation": "Graded per detected citation that is not supported, against the labeller's account of the source: the suggested action says concretely what to change, and any correction it states matches the source (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    **{
        f"label_{level}": f"Of the detected citations a correct run labels '{level}', the share the run labelled so; NaN when the sample has none detected."
        for level in LEVELS
    },
    "evidence_verbatim": "Share of the evidence quotes the run cites that occur verbatim in a supporting file; NaN when it cites none.",
    "cited_text_verbatim": "Share of the citation records whose cited text occurs verbatim in the document; NaN when there are none.",
}

SCORE_LABELS = {
    "label_supported": "Supported",
    "label_partially_supported": "Partial",
    "label_unsupported": "Unsupported",
    "label_unverifiable": "Unverifiable",
    "evidence_verbatim": "Evidence verbatim",
    "cited_text_verbatim": "Cited text verbatim",
    "rationale_matches_source": "Rationale right",
    "action_fixes_citation": "Action fixes",
}
