"""The shared source checks for web-search workflows: citation parsing and the source scores."""

import math
from unittest.mock import AsyncMock, patch

import pytest
from inspect_ai.model import ModelName
from inspect_ai.solver import TaskState

from evals_inspectai.common import api_solver
from evals_inspectai.common.api_solver import api_workflow_solver
from evals_inspectai.common.issue_inventory import InventoryRecord, inventory_to_sample, resolve_record
from evals_inspectai.common.simple_deep_agent_types import IssueItem
from evals_inspectai.common.source_citations import document_references, issue_citations, parse_citation, source_scores

DOC = (
    "# HTTP (2015)\n\nHTTP/1.1 is the latest version.\n\n## References\n\n"
    "1. Fielding, R., et al. (1999). RFC 2616: Hypertext Transfer Protocol -- HTTP/1.1. IETF.\n"
)
RECORD = InventoryRecord(input=DOC, publication_date="2015-01-01")
INVENTORY = resolve_record(RECORD)


def _issue(long_description: str, title: str = "Update the claim") -> IssueItem:
    return IssueItem(title=title, description="HTTP/2 superseded it.", long_description=long_description, severity="medium")


@pytest.mark.parametrize(
    ("line", "author", "year"),
    [
        ("**Source:** Bentivogli, L., & Federico, M. (2018). *Neural versus phrase-based MT*. https://doi.org/10.1016/j.csl.2017.11.004", "Bentivogli", 2018),
        ("- **Conflicting:** Thomson, M., & Benfield, C. (Eds.). (2022, June). *HTTP/2* (RFC 9113). DOI: https://doi.org/10.17487/RFC9113", "Thomson", 2022),
        ("1. Ebbinghaus, H. (1885). Memory: A Contribution to Experimental Psychology.", "Ebbinghaus", 1885),
        ("Stahlberg, F. 2020. Neural machine translation: A review. https://jair.org/index.php/jair/article/view/12007", "Stahlberg", 2020),
        ("**Recommended source (new; quality: high; direction: mixed):** de Bruin, A., & Della Sala, S. (2015). *Publication bias?* https://doi.org/10.1177/0956797614557866", "Bruin", 2015),
        ("**Recommended source (new).** Alan B. Krueger (1999), “Experimental Estimates,” QJE. DOI: https://doi.org/10.1162/003355399556052", "Krueger", 1999),
        ("- Iweala OI, et al. 2021. *Peanut Allergy Diagnosis in a Claims Database (2011-2017).* https://doi.org/10.1016/j.jaip.2020.12.012", "Iweala", 2021),
        ("Brooke N. Macnamara and Alexander P. Burgoyne (2023). Do growth mindset interventions impact achievement? https://doi.org/10.1037/bul0000352", "Macnamara", 2023),
    ],
)
def test_a_reference_line_gives_its_first_author_and_year(line, author, year):
    citation = parse_citation(line)
    assert (citation.first_author, citation.year) == (author, year)


def test_a_doi_is_never_read_as_the_year():
    assert parse_citation("Smith, J. Title. https://doi.org/10.1037/2019.1234").year is None


def test_only_link_bearing_lines_are_citations():
    issue = _issue("**Direction:** Conflicting. Belshe et al. (2015) standardized HTTP/2.\n\n**Source:** Belshe, M. (2015). RFC 7540. https://www.rfc-editor.org/rfc/rfc7540")
    assert [(c.first_author, c.year) for c in issue_citations(issue)] == [("Belshe", 2015)]


def test_the_documents_reference_list_is_read_under_its_heading():
    assert [(c.first_author, c.year) for c in document_references(DOC)] == [("Fielding", 1999)]
    assert document_references("# Note\n\n## References\n\nNone.\n") == []


def test_sources_must_postdate_a_live_report_and_be_new():
    new = _issue("**Source:** Belshe, M. (2015). RFC 7540. https://www.rfc-editor.org/rfc/rfc7540")
    old = _issue("**Source:** Fielding, R. (1999). RFC 2616. https://www.rfc-editor.org/rfc/rfc2616")
    values, note = source_scores([new, old], INVENTORY, "Belshe and Fielding", after=True, new_sources_only=True)
    assert values == {"cites_source": 1.0, "sources_in_window": 0.5, "report_lists_sources": 1.0, "not_already_cited": 0.5}
    assert "before 2015" in note and "already in the document's references" in note


def test_sources_must_predate_a_literature_review():
    later = _issue("**Recommended source:** Orben, A. (2019). Screens. https://doi.org/10.1038/s41562-018-0506-1")
    values, note = source_scores([later], INVENTORY, "", after=False, new_sources_only=False)
    assert values["sources_in_window"] == 0.0 and "after 2015" in note
    assert values["report_lists_sources"] == 0.0 and "report does not name" in note
    assert "not_already_cited" not in values


def test_an_existing_reference_recommended_in_a_literature_review_goes_through_every_check():
    existing = _issue("Cite Fielding et al. (1999) here as well.", title="Cite the existing Fielding reference")
    bare = _issue("Some newer work shows this.")
    values, note = source_scores([existing, bare], INVENTORY, "", after=False, new_sources_only=False)
    assert values["cites_source"] == 0.5 and "no dated, linked citation" in note
    assert values["sources_in_window"] == 1.0
    assert values["report_lists_sources"] == 0.0 and "Fielding" in note


def test_a_live_report_gets_no_credit_for_naming_the_documents_own_source():
    reused = _issue("Cite Fielding et al. (1999) here as well.", title="Cite the existing Fielding reference")
    values, note = source_scores([reused], INVENTORY, "Fielding", after=True, new_sources_only=True)
    assert values["cites_source"] == 0.0 and "no dated, linked citation" in note


def test_source_checks_are_nan_with_nothing_to_judge():
    values, _ = source_scores([], INVENTORY, "", after=True, new_sources_only=True)
    assert all(math.isnan(v) for v in values.values())
    undated = resolve_record(InventoryRecord(input=DOC))
    values, _ = source_scores([_issue("**Source:** Belshe, M. (2015). https://x.org")], undated, "Belshe", after=True, new_sources_only=False)
    assert math.isnan(values["sources_in_window"]) and values["cites_source"] == 1.0


def test_a_records_publication_date_reaches_the_sample_metadata():
    assert inventory_to_sample(INVENTORY).metadata["publication_date"] == "2015-01-01"
    assert "publication_date" not in inventory_to_sample(resolve_record(InventoryRecord(input=DOC))).metadata


@pytest.mark.asyncio
async def test_the_dated_solver_puts_the_publication_date_on_the_project():
    sample = inventory_to_sample(INVENTORY)
    state = TaskState(ModelName("none/none"), sample_id=1, epoch=1, input=sample.input, messages=[], metadata=sample.metadata)
    create = AsyncMock(return_value="project-1")
    poll = AsyncMock(return_value={"state": {"result": {"issues": []}}, "run": {"id": "r"}})
    with patch.object(api_solver, "create_project_and_start_workflows", create), patch.object(api_solver, "poll_until_complete", poll):
        await api_workflow_solver("live_reports_v2")(state, AsyncMock())
    assert create.await_args.kwargs["publication_date"] == "2015-01-01"
    assert '"issues": []' in state.output.completion
