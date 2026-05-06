"""Manifest for the Recommendation Check workflow.

Verifies that recommendations made in the document are directly supported by
the findings/evidence presented elsewhere in the same document. Complements
citation-grounding workflows: those check that claims are backed by external
sources; this one checks that recommendations are backed by the document's
own findings.
"""

from lib.workflows.models import WorkflowRunType
from lib.workflows.simple_deep_agent.manifest_base import SimpleDeepAgentManifest

_USER_PROMPT = """\
Evaluate whether each recommendation in the document is directly supported \
by findings presented elsewhere in the same document.

A "finding" is empirical evidence, analysis, data, or a substantive observation \
presented in the body of the document (e.g. results, case study outcomes, \
quantitative analysis, expert interviews summarized within the document). \
A finding must come from the document itself — external citations alone do \
not count, since other analyses cover citation grounding.

## Procedure

1. **Locate recommendations.** Recommendations typically live in a section \
titled "Recommendations", "Findings and Recommendations", "Conclusions and \
Recommendations", or similar. They may also appear in the executive summary, \
conclusions, or policy implications. A document often contains **multiple \
recommendation sections** — for example, a high-level summary near the \
beginning and a detailed version at the end. **Check all of them**, and treat \
each distinct recommendation as a separate item even when multiple appear in \
the same paragraph or bullet list. If the same recommendation is restated in \
multiple sections (e.g. once in a summary and again in a detailed section), \
evaluate **each occurrence separately** — wording often differs slightly \
between restatements, and a difference in phrasing can change whether the \
document's findings actually support it.

2. **For each recommendation, search the document for supporting findings.** \
Read the body, results, and analysis sections to identify the finding(s) \
that directly justify the recommendation. Quote the supporting text and note \
where it appears.

3. **Classify each recommendation as one of:**

   - **supported** — at least one finding in the document directly backs \
**the recommendation as worded**, including any specific numeric thresholds, \
percentages, time horizons, or scope qualifiers it contains. If the \
recommendation introduces a new specific (e.g. "cap at 6 hours", "increase \
by at least 25 percent", "within 18 months") that is not itself stated or \
clearly implied by a finding, do **not** classify as supported — choose \
partially_supported instead.

   - **partially_supported** — a relevant finding exists in the document and \
substantively backs the *direction* of the recommendation, but one of the \
following applies:
     * The recommendation adds a specific threshold, magnitude, or time \
horizon that is not directly grounded in a finding.
     * The recommendation addresses only part of what the findings cover, \
or covers more than the findings do (a small inferential extension).
     * The recommendation extrapolates from a measured population/site to \
a closely related but unmeasured one (e.g. from one ward to another ward \
in the same hospital, or from a pilot region to neighbouring regions of \
the same kind).
     * The recommendation is stated weakly or generically but the underlying \
direction is consistent with the findings.

   - **unsupported** — use this classification when **any** of the following \
apply:
     * **Out-of-scope population, geography, or domain.** The recommendation \
explicitly applies to a group, location, or domain the document's findings \
did not cover at all (e.g. recommending changes for "contractors worldwide" \
when the study covered only in-house staff at a single organisation, or for \
"oncology wards" when only cardiology was studied). Even when the underlying \
intervention is shown to work in the studied scope, extending to an entirely \
unstudied scope is **unsupported, not partially_supported**.
     * **No relevant finding.** The document contains no finding that \
addresses the subject of the recommendation at all (e.g. recommending \
equipment replacement when no equipment audit was performed).
     * **Contradicted by findings.** The available findings directly \
contradict the recommendation (e.g. recommending an intervention to \
restore beach width when findings explicitly state no beach-width change \
was observed).

   **Boundary rule (when in doubt between partially_supported and \
unsupported):** If the recommendation's *subject* (the population, location, \
domain, or measurement) was studied at all in the document — even partially \
— it is at most partially_supported. If the *subject itself* was never \
measured, it is unsupported.

## Reporting

- For each **supported** recommendation, emit one issue with \
**severity: none** — these are informational and confirm the recommendation \
is properly grounded.
- For each **partially_supported** recommendation, emit one issue with \
**severity: medium**.
- For each **unsupported** recommendation, emit one issue with \
**severity: high**.

Emit one issue per recommendation occurrence (a recommendation restated in \
multiple sections produces multiple issues, evaluated independently).
"""


class RecommendationCheckManifest(SimpleDeepAgentManifest):
    """Checks that recommendations are supported by the document's own findings."""

    type = WorkflowRunType.RECOMMENDATION_CHECK
    name = "Recommendation Check"
    description = (
        "Are the document's recommendations supported by its own findings? "
        "Flags recommendations that lack backing evidence in the body, or "
        "where the evidence is weak, indirect, or contradictory."
    )
    required_dependencies = [WorkflowRunType.DOCUMENT_PROCESSING]
    is_experimental = False

    user_prompt = _USER_PROMPT
