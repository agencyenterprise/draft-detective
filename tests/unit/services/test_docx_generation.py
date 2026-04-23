"""Tests for DOCX generation helper functions"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from lib.models.issue import Issue
from lib.services.docx.manipulator import CommentSeverity, DocxComment, issue_to_comment
from lib.workflows.citation_suggester.manifest import CitationSuggesterManifest
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType

_FAKE_PROJECT_ID = uuid.uuid4()
_FAKE_WORKFLOW_RUN_ID = uuid.uuid4()


@dataclass
class _FakeChunk:
    chunk_index: int
    content: str
    start_line: int
    end_line: int


def _make_issue(
    title: str,
    description: str,
    severity: SeverityEnum,
    workflow_type: WorkflowRunType,
    chunk_indices: list[int] | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> Issue:
    """Create an Issue instance for testing without hitting the DB."""
    now = datetime.now(UTC)
    return Issue(
        id=uuid.uuid4(),
        project_id=_FAKE_PROJECT_ID,
        workflow_run_id=_FAKE_WORKFLOW_RUN_ID,
        issue_hash=uuid.uuid4().hex[:64],
        title=title,
        description=description,
        severity=severity,
        workflow_type=workflow_type,
        chunk_indices=chunk_indices,
        start_line=start_line,
        end_line=end_line,
        created_at=now,
        updated_at=now,
    )


def convert_citation_suggester_state_issues(state: CitationSuggesterState):
    manifest = CitationSuggesterManifest()
    return manifest.convert_state_to_issues(state, [])


class TestIssueToComment:
    """Tests for the issue_to_comment function"""

    def test_converts_issue_to_comment_successfully(self):
        issue = _make_issue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            start_line=1,
            end_line=3,
        )
        chunks = [_FakeChunk(0, "The claim content here", 1, 3)]
        paragraph_line_ranges = {0: (1, 3)}

        comment = issue_to_comment(issue, chunks, paragraph_line_ranges)

        assert comment is not None
        assert isinstance(comment, DocxComment)
        assert comment.paragraph_index == 0
        assert "Unsupported Claim" in comment.comment_text
        assert "This claim lacks evidence" in comment.comment_text
        assert comment.severity == CommentSeverity.HIGH
        assert comment.get_author() == "🚨 High Priority"

    def test_falls_back_to_chunk_indices_for_legacy_issue(self):
        """Issues pre-dating the line-range migration only carry chunk_indices."""
        issue = _make_issue(
            title="Legacy issue",
            description="Only has chunk_indices",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            chunk_indices=[1],
        )
        chunks = [
            _FakeChunk(0, "Intro", 1, 2),
            _FakeChunk(1, "Body with the claim", 3, 5),
        ]
        paragraph_line_ranges = {0: (1, 2), 1: (3, 5)}

        comment = issue_to_comment(issue, chunks, paragraph_line_ranges)

        assert comment is not None
        assert comment.paragraph_index == 1

    def test_returns_none_when_line_range_unresolvable(self):
        issue = _make_issue(
            title="Invalid reference",
            description="Reference not found",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.REFERENCE_VALIDATION,
        )
        chunks: list[_FakeChunk] = []

        comment = issue_to_comment(issue, chunks, {})

        assert comment is None

    def test_returns_none_when_no_paragraph_overlaps(self):
        issue = _make_issue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            start_line=100,
            end_line=110,
        )
        paragraph_line_ranges = {0: (1, 10), 1: (11, 20)}

        comment = issue_to_comment(issue, [], paragraph_line_ranges)

        assert comment is None

    def test_share_link_anchor_uses_line_range(self):
        issue = _make_issue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            start_line=5,
            end_line=15,
        )
        paragraph_line_ranges = {0: (1, 20)}

        comment = issue_to_comment(
            issue, [], paragraph_line_ranges, share_token="share-token-abc"
        )

        assert comment is not None
        assert comment.share_link is not None
        assert comment.share_link.endswith("#L5-15")

    def test_medium_severity_uses_correct_author(self):
        issue = _make_issue(
            title="Partially Supported",
            description="Some evidence found",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION,
            start_line=1,
            end_line=1,
        )
        paragraph_line_ranges = {0: (1, 1)}

        comment = issue_to_comment(issue, [], paragraph_line_ranges)

        assert comment.severity == CommentSeverity.MEDIUM
        assert comment.get_author() == "⚠️ Medium Priority"
        assert comment.get_initials() == "MP"

    def test_low_severity_uses_correct_author(self):
        issue = _make_issue(
            title="Minor Note",
            description="Just a suggestion",
            severity=SeverityEnum.LOW,
            workflow_type=WorkflowRunType.CITATION_SUGGESTER,
            start_line=1,
            end_line=1,
        )
        paragraph_line_ranges = {0: (1, 1)}

        comment = issue_to_comment(issue, [], paragraph_line_ranges)

        assert comment.severity == CommentSeverity.LOW
        assert comment.get_author() == "💡 Low Priority"
        assert comment.get_initials() == "LP"


class TestBuildCitationSuggestionIssues:
    """Tests for the convert_citation_suggester_state_issues function"""

    @pytest.fixture
    def base_state(self) -> CitationSuggesterState:
        """Create a base state for testing"""
        return CitationSuggesterState(
            type=WorkflowRunType.CITATION_SUGGESTER,
            file_id="test-file-id",
            config=CitationSuggesterWorkflowConfig(
                type=WorkflowRunType.CITATION_SUGGESTER,
                project_id="test-project",
            ),
            citation_suggestions=[],
        )

    def test_returns_empty_list_when_no_citation_suggestions(self, base_state):
        issues = convert_citation_suggester_state_issues(base_state)
        assert issues == []

    def test_creates_issue_for_add_citation_action(self, base_state):
        from lib.agents.citation_suggester import (
            CitationSuggestionResultWithClaimIndex,
            ConfidenceInRecommendation,
            PublicationQuality,
            RecommendedAction,
            Reference,
        )
        from lib.agents.literature_review import ReferenceType

        base_state.citation_suggestions = [
            CitationSuggestionResultWithClaimIndex(
                claim_index=0,
                chunk_index=0,
                rationale="This claim needs supporting evidence",
                relevant_references=[
                    Reference(
                        title="Important Study 2024",
                        type=ReferenceType.PEER_REVIEWED_PUBLICATION,
                        link="https://example.com/study",
                        bibliography_info="Author. Important Study. 2024.",
                        is_already_cited_elsewhere=False,
                        index_of_associated_existing_reference=-1,
                        publication_quality=PublicationQuality.HIGH_IMPACT_PUBLICATION,
                        related_excerpt="The claim text",
                        related_excerpt_from_reference="Supporting evidence",
                        rationale="Directly supports the claim",
                        recommended_action=RecommendedAction.ADD_NEW_CITATION,
                        explanation_for_recommended_action="Add citation here",
                        confidence_in_recommendation=ConfidenceInRecommendation.HIGH,
                    )
                ],
            )
        ]

        issues = convert_citation_suggester_state_issues(base_state)

        assert len(issues) == 1
        assert isinstance(issues[0], DocumentIssue)
        assert issues[0].chunk_indices == [0]
        assert issues[0].title == "Citation Suggestion"
        assert issues[0].severity == SeverityEnum.LOW
        assert "This claim needs supporting evidence" in issues[0].description
        assert "Important Study 2024" in issues[0].description

    def test_ignores_no_action(self, base_state):
        from lib.agents.citation_suggester import (
            CitationSuggestionResultWithClaimIndex,
            ConfidenceInRecommendation,
            PublicationQuality,
            RecommendedAction,
            Reference,
        )
        from lib.agents.literature_review import ReferenceType

        base_state.citation_suggestions = [
            CitationSuggestionResultWithClaimIndex(
                claim_index=0,
                chunk_index=0,
                rationale="Citation is already appropriate",
                relevant_references=[
                    Reference(
                        title="Existing Reference",
                        type=ReferenceType.PEER_REVIEWED_PUBLICATION,
                        link="https://example.com/existing",
                        bibliography_info="Author. Existing Reference. 2023.",
                        is_already_cited_elsewhere=True,
                        index_of_associated_existing_reference=1,
                        publication_quality=PublicationQuality.HIGH_IMPACT_PUBLICATION,
                        related_excerpt="The cited text",
                        related_excerpt_from_reference="Reference text",
                        rationale="Already cited",
                        recommended_action=RecommendedAction.NO_ACTION,
                        explanation_for_recommended_action="No changes needed",
                        confidence_in_recommendation=ConfidenceInRecommendation.HIGH,
                    )
                ],
            )
        ]

        issues = convert_citation_suggester_state_issues(base_state)

        assert issues == []

    def test_includes_replace_existing_reference_action(self, base_state):
        from lib.agents.citation_suggester import (
            CitationSuggestionResultWithClaimIndex,
            ConfidenceInRecommendation,
            PublicationQuality,
            RecommendedAction,
            Reference,
        )
        from lib.agents.literature_review import ReferenceType

        base_state.citation_suggestions = [
            CitationSuggestionResultWithClaimIndex(
                claim_index=0,
                chunk_index=0,
                rationale="Better reference available",
                relevant_references=[
                    Reference(
                        title="New Better Study 2025",
                        type=ReferenceType.PEER_REVIEWED_PUBLICATION,
                        link="https://example.com/new-study",
                        bibliography_info="Author. New Better Study. 2025.",
                        is_already_cited_elsewhere=False,
                        index_of_associated_existing_reference=2,
                        publication_quality=PublicationQuality.HIGH_IMPACT_PUBLICATION,
                        related_excerpt="The outdated claim",
                        related_excerpt_from_reference="Updated evidence",
                        rationale="More recent and comprehensive",
                        recommended_action=RecommendedAction.REPLACE_EXISTING_REFERENCE,
                        explanation_for_recommended_action="Replace old reference",
                        confidence_in_recommendation=ConfidenceInRecommendation.HIGH,
                    )
                ],
            )
        ]

        issues = convert_citation_suggester_state_issues(base_state)

        assert len(issues) == 1
        assert "New Better Study 2025" in issues[0].description

    def test_limits_references_to_three(self, base_state):
        from lib.agents.citation_suggester import (
            CitationSuggestionResultWithClaimIndex,
            ConfidenceInRecommendation,
            PublicationQuality,
            RecommendedAction,
            Reference,
        )
        from lib.agents.literature_review import ReferenceType

        many_references = [
            Reference(
                title=f"Reference {i}",
                type=ReferenceType.PEER_REVIEWED_PUBLICATION,
                link=f"https://example.com/ref{i}",
                bibliography_info=f"Author. Reference {i}. 2024.",
                is_already_cited_elsewhere=False,
                index_of_associated_existing_reference=-1,
                publication_quality=PublicationQuality.HIGH_IMPACT_PUBLICATION,
                related_excerpt="Some text",
                related_excerpt_from_reference="Reference text",
                rationale=f"Explanation {i}",
                recommended_action=RecommendedAction.ADD_NEW_CITATION,
                explanation_for_recommended_action="Add citation",
                confidence_in_recommendation=ConfidenceInRecommendation.MEDIUM,
            )
            for i in range(5)
        ]

        base_state.citation_suggestions = [
            CitationSuggestionResultWithClaimIndex(
                claim_index=0,
                chunk_index=0,
                rationale="Multiple references available",
                relevant_references=many_references,
            )
        ]

        issues = convert_citation_suggester_state_issues(base_state)

        assert len(issues) == 1
        # Should only include first 3 references
        assert "Reference 0" in issues[0].description
        assert "Reference 1" in issues[0].description
        assert "Reference 2" in issues[0].description
        assert "Reference 3" not in issues[0].description
        assert "Reference 4" not in issues[0].description
