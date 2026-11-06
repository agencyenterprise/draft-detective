"""What Advocacy & Tone is judged on, beyond the generic layers.

The skill fixes two things about every issue it reports, so they are checked
deterministically over all reported issues, not only the ones matched to an
expected issue: the title is one of its three, and the issue's line range is the
offending sentence's, which in these documents is a single line. Severity is the agent's
judgment, so it is not scored.
It also names the sections to skip; no reported issue may sit in one.

The workflow proposes no edits, so its fix lives in the suggested action. Two
graded criteria read it per detected issue: the action says concretely how to
make this sentence neutral (graded against the paragraph, which is all the
grader needs to see the whole sentence), and any wording it proposes keeps the
sentence's claim without adding to it (graded against the whole report, since a
rewrite may fairly restate a figure from elsewhere in it).
"""

import math
import re
from collections.abc import Sequence

from evals_inspectai.common.issue_inventory import ResolvedInventory, normalize
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

TITLES = (
    "Trigger Words Detected",
    "Advocacy Language Detected",
    "Subjective Tone Detected",
)

# The skill: "Do not flag matches inside sections whose heading contains `author`,
# `reference`, `bibliography`, `appendix`, or `acknowledgment`." Matched as substrings,
# as the skill words it, so "Authors" and "Acknowledgments" are skipped.
SKIPPED_HEADING_WORDS = (
    "author",
    "reference",
    "bibliography",
    "appendix",
    "acknowledgment",
)

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*)$")


def skipped_lines(document: str) -> set[int]:
    """The 1-indexed lines inside a skipped section: under a heading whose text
    contains one of the skipped words, down to the next heading of the same or a
    higher level, subsections included."""
    stack: list[tuple[int, bool]] = []
    skipped: set[int] = set()
    for number, line in enumerate(document.split("\n"), 1):
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            text = heading.group(2).lower()
            stack.append((level, any(word in text for word in SKIPPED_HEADING_WORDS)))
        if any(skip for _, skip in stack):
            skipped.add(number)
    return skipped


def _share(passed: Sequence[bool]) -> float:
    return sum(passed) / len(passed) if passed else math.nan


def tone_scores(
    issues: Sequence[IssueItem], inventory: ResolvedInventory
) -> tuple[dict[str, float], str]:
    """``known_titles``: share of reported issues titled exactly as one of the skill's
    three kinds. ``one_line_range``: share of reported issues whose range is a single
    line. ``skipped_sections_untouched``: 1 when no reported issue's range reaches into
    a skipped section, 0 otherwise, NaN when the document has none. The first two are
    NaN when nothing was reported."""
    known_titles = {normalize(t) for t in TITLES}
    odd = [i.title for i in issues if normalize(i.title) not in known_titles]
    wide = [
        f"{i.start_line}-{i.end_line}" for i in issues if i.start_line != i.end_line
    ]
    skipped = skipped_lines(inventory.document)
    intruding = [
        f"{i.title!r} at {i.start_line}-{i.end_line}"
        for i in issues
        if skipped & set(range(i.start_line, i.end_line + 1))
    ]
    values = {
        "known_titles": _share([normalize(i.title) in known_titles for i in issues]),
        "one_line_range": _share([i.start_line == i.end_line for i in issues]),
        "skipped_sections_untouched": float(not intruding) if skipped else math.nan,
    }
    notes = [f"titles outside the skill's set: {odd}"] if odd else []
    notes += [f"ranges wider than one line: {wide}"] if wide else []
    notes += [f"issues in a skipped section: {intruding}"] if intruding else []
    return values, (
        " | ".join(notes)
        if notes
        else "titles, ranges and skipped sections all as the skill says"
    )


_FLAGGED = (
    "The reviewer flagged the sentence containing the quoted text for non-neutral language in a research report: "
    "a trigger word (a certainty word such as 'clearly', 'undoubtedly', 'always' or 'never' used without "
    "evidence), advocacy language (opinion framing such as 'we believe', 'in our opinion' or 'it is clear that', "
    "or the authors' own push or obligation with words such as 'must', 'requires', 'urgent', 'critical', "
    "'essential' or 'ensuring'), or subjective tone (value judgments or emotional wording). "
)

CONCRETE_CRITERION = _FLAGGED + (
    "The passage shown is the paragraph the sentence sits in. Grade whether the suggested action tells the "
    "author concretely how to make this sentence neutral: it gives neutral wording for the sentence or for the "
    "offending phrase, or it names the exact word or phrase to delete, hedge or replace and says what to put in "
    "its place (for example: replace 'undoubtedly changed' with 'may have changed'; delete 'clearly'; recast "
    "'the state must' as 'the state could consider'; state the finding as the report's result rather than as "
    "the authors' belief). Asking the author to cite supporting evidence as well is fine. Partially correct: it "
    "names the offending word or phrase but only asks the author to reword, hedge, soften or support it without "
    "saying how, for example 'replace \"clearly\" with qualified language', 'replace the evaluative wording with a "
    "factual description', 'recast the sentence as an evidence-based finding': a category of wording is not "
    "wording. Deleting the word outright ('remove \"obviously\"') is a concrete change. Incorrect: advice that "
    "could be pasted onto any flagged sentence ('revise for neutrality', 'use objective language', 'add "
    "supporting evidence') without naming the wording to change."
)

FAITHFUL_CRITERION = _FLAGGED + (
    "The full report is shown. Grade whether any neutral wording the suggested action proposes keeps what the "
    "sentence says, only made neutral: the same subject, the same numbers, the same finding or recommendation. "
    "Hedging a certainty ('may', 'suggests'), attributing or conditioning an opinion, softening a recommendation "
    "('must' to 'could consider'), and dropping loaded or emotional words all keep the claim. Restating a figure "
    "the report gives elsewhere is fine. It is incorrect if the proposed wording adds a claim, cause, number, "
    "citation or piece of evidence the report does not contain, changes or drops a number or finding the "
    "sentence reports, or reverses the sentence's meaning. An action that proposes no wording of its own (it "
    "only names what to change, or asks the author to supply evidence) is correct."
)

JUDGE_CRITERIA = [
    JudgeCriterion(
        key="action_concrete",
        criterion=CONCRETE_CRITERION,
        scope="expected",
        passage="section",
    ),
    JudgeCriterion(
        key="action_faithful",
        criterion=FAITHFUL_CRITERION,
        scope="expected",
        passage="document",
    ),
]

JUDGE_DESCRIPTIONS = {
    "action_concrete": "Graded per detected issue against the sentence's paragraph: the suggested action gives neutral wording or names the exact word to delete, hedge or replace and with what, not generic advice (C=1, P=0.5, I=0).",
    "action_faithful": "Graded per detected issue against the whole report: any wording the suggested action proposes keeps the sentence's subject, numbers and claim and adds nothing the report does not contain (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "known_titles": "Share of reported issues titled exactly as one of the skill's three kinds; NaN when nothing was reported.",
    "one_line_range": "Share of reported issues whose line range is a single line: the skill puts the issue on the offending sentence's line, and every paragraph here is one line. NaN when nothing was reported.",
    "skipped_sections_untouched": "1 when no reported issue reaches into a section whose heading contains author, reference, bibliography, appendix or acknowledgment (subsections included); NaN when the document has none.",
}

SCORE_LABELS = {
    "known_titles": "Known titles",
    "one_line_range": "One-line range",
    "skipped_sections_untouched": "Skipped sections",
    "action_concrete": "Concrete action",
    "action_faithful": "Faithful action",
}
