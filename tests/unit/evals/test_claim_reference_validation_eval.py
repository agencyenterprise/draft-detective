"""The Claim Reference Validation eval: its records, how citation records become issues, and its own checks."""

import collections
import math
from pathlib import Path

from evals_inspectai.common.issue_checks import issue_detection_scores
from evals_inspectai.common.issue_inventory import ResolvedInventory, ResolvedIssue
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.e2e.claim_reference_validation_v2.claim_reference_validation_v2_e2e import (
    claim_reference_validation_v2_e2e,
)
from evals_inspectai.e2e.claim_reference_validation_v2.criteria import (
    JUDGE_CRITERIA,
    LEVELS,
    as_issues,
    evidence_scores,
    label_scores,
    quote_scores,
)
from evals_inspectai.e2e.claim_reference_validation_v2.records import load_claim_records

DATASET = Path("evals_inspectai/e2e/claim_reference_validation_v2/dataset.yaml")
DOC = "# Findings\n\nThe share rose to 93% worldwide (Patel, 2018).\n\nRural closures dominated (Kim, 2023).\n"


def _expected(eid: str, level: str, anchor: str, line: int) -> ResolvedIssue:
    return ResolvedIssue(id=eid, title=level, anchor=anchor, line=line, rationale="r")


INVENTORY = ResolvedInventory(
    document=DOC,
    expected_issues=[
        _expected("patel", "partially_supported", "The share rose to 93% worldwide", 3),
        _expected("kim", "supported", "Rural closures dominated", 5),
    ],
    decoys=[],
    named_titles=list(LEVELS),
)


def _record(level: str, quoted: str, line: int, quotes: tuple[str, ...] = ()) -> dict:
    return {
        "quoted_text": quoted,
        "line_start": line,
        "line_end": line,
        "evidence_alignment": level,
        "rationale": "why",
        "feedback": "fix",
        "evidence_sources": [{"quote": q, "location": "", "file_id": "f"} for q in quotes],
    }


def test_records_are_well_formed():
    records = load_claim_records(DATASET)
    assert len(records) == 22
    expected = [e for r in records for e in r.inventory.expected_issues]
    assert collections.Counter(e.title for e in expected) == {
        "supported": 16,
        "unsupported": 10,
        "partially_supported": 4,
        "unverifiable": 3,
    }
    assert all(e.anchor and e.rationale for e in expected)
    assert all(r.inventory.named_titles == sorted(LEVELS) for r in records)
    no_source = [r for r in records if not r.sources]
    assert len(no_source) == 2, "the unverifiable citation's document and the document with no citations"
    assert sum(1 for r in records if not r.inventory.expected_issues) == 1


def test_task_reads_the_citation_records_and_leaves_severity_unchecked():
    t = claim_reference_validation_v2_e2e()
    assert len(t.dataset) == 22 and len(t.scorer) == 4
    assert "severity_correct" not in t.metadata["metrics"]["issue_checks"]
    assert all(s.metadata and "sources" in s.metadata for s in t.dataset)


def test_citation_records_become_issues_titled_by_their_level():
    (issue,) = as_issues([_record("partially_supported", "93% worldwide", 3)])
    assert issue["title"] == "partially_supported" and issue["long_description"] == "93% worldwide"
    assert issue["severity"] == "medium" and issue["suggested_action"] == "fix"
    (enum,) = as_issues([{**_record("x", "q", 1), "evidence_alignment": {"value": "unsupported"}}])
    assert enum["title"] == "unsupported"


def test_supported_does_not_match_a_partially_supported_report():
    """The reason the eval titles issues with the level itself."""
    issues = [IssueItem(**i) for i in as_issues([_record("partially_supported", "The share rose to 93% worldwide", 3)])]
    supported_only = INVENTORY.model_copy(update={"expected_issues": [_expected("p", "supported", "The share rose to 93% worldwide", 3)]})
    values, _ = issue_detection_scores(issues, supported_only, edits=False, one_to_one=True, severities=False)
    assert values["recall"] == 1.0 and values["title_correct"] == 0.0


def test_swapped_levels_on_one_line_are_both_scored_wrong():
    """Two citations on one line with their levels swapped: pairing on the verdict would match
    each report to the other citation and score both as right."""
    doc = "# Evidence\n\nEarnings rose 12 percent (Mbeki, 2020). The gains lasted five years (Mbeki, 2020).\n"
    inventory = ResolvedInventory(
        document=doc,
        expected_issues=[
            _expected("two_years", "supported", "Earnings rose 12 percent", 3),
            _expected("five_years", "unsupported", "The gains lasted five years", 3),
        ],
        decoys=[],
        named_titles=list(LEVELS),
        pair_on_location=True,
    )
    issues = [
        IssueItem(**i)
        for i in as_issues([_record("unsupported", "Earnings rose 12 percent (Mbeki, 2020).", 3), _record("supported", "The gains lasted five years (Mbeki, 2020).", 3)])
    ]
    values, _ = issue_detection_scores(issues, inventory, edits=False, one_to_one=True, severities=False)
    assert values["recall"] == 1.0 and values["title_correct"] == 0.0
    labels, _ = label_scores(issues, inventory)
    assert labels["label_supported"] == 0.0 and labels["label_unsupported"] == 0.0
    assert all(r.inventory.pair_on_location for r in load_claim_records(DATASET)), "the loader pairs on location"


def test_label_accuracy_is_broken_down_by_the_expected_level():
    issues = [
        IssueItem(**i)
        for i in as_issues([_record("partially_supported", "The share rose to 93% worldwide", 3), _record("partially_supported", "Rural closures dominated", 5)])
    ]
    values, note = label_scores(issues, INVENTORY)
    assert values["label_partially_supported"] == 1.0 and values["label_supported"] == 0.0
    assert math.isnan(values["label_unsupported"]) and math.isnan(values["label_unverifiable"])
    assert "kim: partially_supported, expected supported" in note


def test_evidence_quotes_must_be_verbatim_in_a_source():
    sources = [{"file_name": "patel.md", "markdown": "93% of samples contained at least one\nparticle. Sampling was North American."}]
    records = [_record("partially_supported", "q", 3, ("93% of samples contained at least one particle", "Samples were global"))]
    values, note = evidence_scores(records, sources)
    assert values["evidence_verbatim"] == 0.5 and "Samples were global" in note
    assert math.isnan(evidence_scores([_record("unverifiable", "q", 3)], sources)[0]["evidence_verbatim"])


def test_an_evidence_quote_may_run_across_a_source_heading():
    sources = [{"file_name": "p.md", "markdown": "# Survey\n\n93% of samples had particles.\n\n## Scope\n\nSampling was North American."}]
    records = [_record("partially_supported", "q", 3, ("93% of samples had particles. Sampling was North American.",))]
    assert evidence_scores(records, sources)[0]["evidence_verbatim"] == 1.0


def test_the_action_criterion_checks_corrections_against_the_source_and_skips_supported_citations():
    rationale, action = JUDGE_CRITERIA
    assert (rationale.reads, rationale.reference, rationale.applies_to) == ("analysis", True, None)
    assert (action.reads, action.reference) == ("suggested_action", True), "the grader needs the source's facts"
    assert action.applies_to is not None
    assert not action.applies_to(INVENTORY.expected_issues[1]) and action.applies_to(INVENTORY.expected_issues[0])


def test_cited_text_must_be_verbatim_in_the_document():
    records = [_record("supported", "Rural closures dominated (Kim, 2023).", 5), _record("supported", "Rural closures were most common", 5)]
    values, note = quote_scores(records, DOC)
    assert values["cited_text_verbatim"] == 0.5 and "Rural closures were most common" in note
    assert math.isnan(quote_scores([], DOC)[0]["cited_text_verbatim"])
