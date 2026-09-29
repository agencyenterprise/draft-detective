"""What Inference Validation is judged on, beyond the generic layers.

Detection says whether the run flagged the right sentence; it cannot say
whether it flagged it for the right reason, and a sentence flagged as a
"hasty generalization" when its flaw is survivorship bias is a report the
author cannot act on. So one graded criterion compares the reported analysis
with the labeller's account of the flaw (the expected issue's ``rationale``),
and another grades whether the suggested action repairs that inference.

Three deterministic checks read every reported issue against the skill's
reporting contract: no informational (``none``) issue, since a sound inference
is reported as nothing; the title names the flaw after the
``Invalid Inference:`` prefix; and the long description's Key Sentence is a
verbatim quote from the document, since that quote is how the author finds the
sentence.
"""

import math
import re
from typing import Optional, Sequence

from evals_inspectai.common.issue_inventory import ResolvedInventory, quoted_verbatim
from evals_inspectai.common.issue_judge import JudgeCriterion
from evals_inspectai.common.simple_deep_agent_types import IssueItem

TITLE = "Invalid Inference"
_TITLE_RE = re.compile(rf"^{TITLE}:\s*\S", re.I)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")
# Markdown emphasis and quote marks a key sentence may be wrapped in.
_WRAPPING = "*_\"'“”‘’ "


def key_sentence(long_description: Optional[str]) -> Optional[str]:
    """The block-quoted text under the long description's ``Key Sentence`` heading, or
    None when there is no such heading or nothing is quoted under it."""
    lines = (long_description or "").split("\n")
    start = next((i for i, line in enumerate(lines) if re.match(r"^\s*#{1,6}\s+key sentence\s*$", line, re.I)), None)
    if start is None:
        return None
    quoted: list[str] = []
    for line in lines[start + 1 :]:
        if _HEADING_RE.match(line):
            break
        if line.lstrip().startswith(">"):
            quoted.append(line.lstrip()[1:].strip())
    text = " ".join(q for q in quoted if q).strip(_WRAPPING)
    return text or None


def inference_scores(issues: Sequence[IssueItem], inventory: ResolvedInventory) -> tuple[dict[str, float], str]:
    """``no_informational``: share of reported issues whose severity is not ``none``.
    ``title_names_flaw``: share titled ``Invalid Inference: <label>``.
    ``key_sentence_quoted``: share whose long description quotes, under a Key Sentence
    heading, text found verbatim in the document. Each is NaN when nothing was reported."""
    if not issues:
        return {"no_informational": math.nan, "title_names_flaw": math.nan, "key_sentence_quoted": math.nan}, "nothing reported"
    informational = [i.title for i in issues if i.severity.lower() == "none"]
    untitled = [i.title for i in issues if not _TITLE_RE.match(i.title.strip())]
    unquoted = [i.title for i in issues if not ((q := key_sentence(i.long_description)) and quoted_verbatim(q, inventory.document))]
    n = len(issues)
    values = {
        "no_informational": 1 - len(informational) / n,
        "title_names_flaw": 1 - len(untitled) / n,
        "key_sentence_quoted": 1 - len(unquoted) / n,
    }
    notes = [f"informational issues: {informational}"] if informational else []
    notes += [f"titles without the flaw label: {untitled}"] if untitled else []
    notes += [f"no verbatim key sentence: {unquoted}"] if unquoted else []
    return values, " | ".join(notes) if notes else "reporting contract met"


FLAW_CRITERION = (
    "The reviewer reported that a sentence of a document draws a logically invalid inference, and the labeller "
    "has described what is actually wrong with it. Grade whether the reviewer's analysis identifies the same "
    "inferential error: the same gap between premise and conclusion, in any words (naming the fallacy is not "
    "required). It is correct if it names that gap, even with additional sound observations. It is partially "
    "correct if it gestures at the gap but its main explanation is a different or vaguer problem. It is incorrect "
    "if it flags the sentence for a different reason, only says the argument is weak or needs more evidence "
    "without saying why the conclusion does not follow, or misstates what the document says."
)

REPAIR_CRITERION = (
    "The reviewer reported that a sentence of a document draws a logically invalid inference, and the passage it "
    "sits in is shown. Grade whether the suggested action tells the author concretely how to repair this "
    "inference: bound the conclusion to what the premises support (saying to what population, period or "
    "conditions), name the evidence or comparison that would support it (a control group, the other causes to "
    "rule out, the missing data), or restate the claim so it follows. Generic advice that fits any argument "
    "(\"provide more evidence\", \"strengthen the reasoning\", \"avoid fallacies\") is incorrect. An action that "
    "would introduce a new unsupported claim is incorrect."
)

JUDGE_CRITERIA = [
    JudgeCriterion(key="flaw_identified", criterion=FLAW_CRITERION, scope="expected", passage="section", reads="analysis", reference=True),
    JudgeCriterion(key="action_repairs", criterion=REPAIR_CRITERION, scope="expected", passage="section"),
]

JUDGE_DESCRIPTIONS = {
    "flaw_identified": "Graded per detected issue against the labeller's account of the flaw: the reported analysis names the same premise-to-conclusion gap (C=1, P=0.5, I=0).",
    "action_repairs": "Graded per detected issue against its passage: the suggested action says concretely how to repair this inference, not advice that fits any argument (C=1, P=0.5, I=0).",
}
OWN_DESCRIPTIONS = {
    "no_informational": "Share of reported issues whose severity is not 'none': a sound inference is reported as nothing. NaN when nothing was reported.",
    "title_names_flaw": "Share of reported issues titled 'Invalid Inference: <label for the flaw>'. NaN when nothing was reported.",
    "key_sentence_quoted": "Share of reported issues whose long description quotes, under 'Key Sentence', text found verbatim in the document. NaN when nothing was reported.",
}

SCORE_LABELS = {
    "no_informational": "No 'none'",
    "title_names_flaw": "Title names flaw",
    "key_sentence_quoted": "Key sentence quoted",
    "flaw_identified": "Flaw identified",
    "action_repairs": "Action repairs",
}
