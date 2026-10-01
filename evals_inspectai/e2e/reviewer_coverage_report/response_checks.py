"""Checks on how the coverage report handles the author's response memos.

When the author's replies are supplied, the skill has the report reproduce each
reply verbatim under the reviewer point it answers, as a separately labelled
quote, and put "No author response to this point" in that slot when a point
went unanswered. When none are supplied, the report must say so in its header,
since every "declined with rationale" verdict then rests on reasons inferred
from the draft, and it must not present any text as the author's reply. A reply
slot holding only the placeholder is fine either way: it tells the reader the
point has no answer, which is true.

Every sample reports both keys, with or without response memos, because Inspect
raises when a declared metric key is missing from any score. Each check
therefore tests the half of the rule that applies to the sample it is given.

Whether the verdicts weigh the replies correctly (a claimed change the draft
does not show, a decline whose only reason is in the reply) is a judgement, and
is graded by each sample's `scenario_trap`.
"""

import re
from typing import Any

from evals_inspectai.common.html_report import HtmlReport, normalize

# The placeholder the skill names, matched on normalised (lowercased) text.
_NO_RESPONSE_SLOT = "no author response to this point"

# A label presenting text as the author's reply. Loose on punctuation, so
# "Author response (verbatim)", "Author's reply, verbatim" and the like all
# count, but anchored on "verbatim": a sentence merely discussing the author's
# response is not a label.
_AUTHOR_LABEL = re.compile(r"author(?:'s)?\s+(?:response|reply)\W{0,3}verbatim")

# A header line saying the replies were not supplied, in either word order:
# "no author response memos were supplied", "response memos: none".
_NONE_SUPPLIED = re.compile(
    r"\b(?:no|without)\b[^.]{0,40}\bresponse memos?\b"
    r"|\bresponse memos?\b[^.]{0,40}\b(?:none|not|no)\b"
)


def _has_responses(meta: dict[str, Any]) -> bool:
    return bool(meta.get("author_probes"))


def _under_author_label(report: HtmlReport, snippet: str) -> bool:
    """Whether `snippet` sits in the block a reply label introduces.

    The skill asks for a labelled quote styled apart from the reviewer's text,
    not for a particular element: a tinted, bordered `<div>` under an "Author
    response (verbatim)" label meets it as well as a `<blockquote>` does. So
    the reply counts as marked when the nearest reply label before it is not
    separated from it by a verdict or another verbatim label.
    """
    position = report.text.find(normalize(snippet))
    if position < 0:
        return False
    labels = [m for m in _AUTHOR_LABEL.finditer(report.text, 0, position)]
    if not labels:
        return False
    between = report.text[labels[-1].end() : position]
    return "verbatim" not in between and "verdict" not in between


def _marked_as_reply(report: HtmlReport, snippet: str) -> bool:
    return report.quotes(snippet) or _under_author_label(report, snippet)


def _invented_replies(report: HtmlReport) -> list[str]:
    """Reply labels followed by anything other than the placeholder."""
    invented = []
    for match in _AUTHOR_LABEL.finditer(report.text):
        following = report.text[match.end() : match.end() + 80].lstrip(" ):.-")
        if not following.startswith(_NO_RESPONSE_SLOT):
            invented.append(following[:60])
    return invented


def check_author_verbatim(
    report: HtmlReport, meta: dict[str, Any]
) -> tuple[bool, str]:
    """Replies reproduced verbatim inside quotes, or none invented.

    With response memos, the probes are distinctive sentences drawn from every
    reply, and each must be marked as the author's: inside a quote, or in the
    block under a reply label. Without them, the report
    must not label any text as the author's reply, though a slot holding only
    the placeholder is allowed.
    """
    if not _has_responses(meta):
        invented = _invented_replies(report)
        return (
            not invented,
            "no author replies presented"
            if not invented
            else f"{len(invented)} reply slot(s) carry text without response memos; first: {invented[0]!r}",
        )

    probes: list[str] = meta["author_probes"]
    missing = [p for p in probes if not report.contains(p)]
    unmarked = [p for p in probes if report.contains(p) and not _marked_as_reply(report, p)]
    problems = []
    if missing:
        problems.append(f"first missing: {missing[0][:60]!r}")
    if unmarked:
        problems.append(
            f"{len(unmarked)} reply probe(s) neither quoted nor under a reply label"
        )
    return (
        not problems,
        f"{len(probes) - len(missing)}/{len(probes)} reply probes reproduced"
        + ("; " + "; ".join(problems) if problems else ""),
    )


def check_response_slots(
    report: HtmlReport, meta: dict[str, Any]
) -> tuple[bool, str]:
    """The unanswered-point slot is filled, or the header says none were given.

    With response memos, a sample whose memos leave a point unanswered must show
    the skill's placeholder. Without them, Part 1 must say no response memos
    were supplied.
    """
    if not _has_responses(meta):
        stated = _NONE_SUPPLIED.search(report.part1)
        return (
            stated is not None,
            "Part 1 says no response memos were supplied"
            if stated
            else "Part 1 does not say that no response memos were supplied",
        )

    if not meta.get("expects_unanswered_point"):
        return True, "every point has a reply in this sample"
    present = _NO_RESPONSE_SLOT in report.text
    return (
        present,
        "unanswered point marked with the placeholder"
        if present
        else f"no {_NO_RESPONSE_SLOT!r} slot for the point the replies skip",
    )
