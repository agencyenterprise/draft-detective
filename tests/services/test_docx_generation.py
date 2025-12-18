"""Tests for DOCX generation helper functions"""

import pytest

from lib.services.docx.manipulator import CommentSeverity, DocxComment, issue_to_comment
from lib.services.file import FileDocument
from lib.workflows.citation_suggester.manifest import CitationSuggesterManifest
from lib.workflows.citation_suggester.state import (
    CitationSuggesterState,
    CitationSuggesterWorkflowConfig,
)
from lib.workflows.claim_substantiation.state import DocumentIssue, SeverityEnum


def convert_citation_suggester_state_issues(state: CitationSuggesterState):
    manifest = CitationSuggesterManifest()
    return manifest.convert_state_to_issues(state, None)


class TestIssueToComment:
    """Tests for the issue_to_comment function"""

    def test_converts_issue_to_comment_successfully(self):
        issue = DocumentIssue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            severity=SeverityEnum.HIGH,
            chunk_index=0,
        )
        chunk_content_map = {0: "The claim content here"}

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment is not None
        assert isinstance(comment, DocxComment)
        assert comment.chunk_index == 0
        assert comment.text == "The claim content here"
        assert "Unsupported Claim" in comment.comment_text
        assert "This claim lacks evidence" in comment.comment_text
        assert comment.severity == CommentSeverity.HIGH
        assert comment.get_author() == "🚨 High Priority"

    def test_returns_none_when_chunk_index_is_none(self):
        issue = DocumentIssue(
            title="Invalid reference",
            description="Reference not found",
            severity=SeverityEnum.HIGH,
            chunk_index=None,
        )
        chunk_content_map = {0: "Some content"}

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment is None

    def test_returns_none_when_chunk_not_in_map(self):
        issue = DocumentIssue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.MEDIUM,
            chunk_index=99,  # Not in the map
        )
        chunk_content_map = {0: "Some content", 1: "Other content"}

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment is None

    def test_returns_none_when_chunk_content_is_empty(self):
        issue = DocumentIssue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.LOW,
            chunk_index=0,
        )
        chunk_content_map = {0: ""}  # Empty content

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment is None

    def test_medium_severity_uses_correct_author(self):
        issue = DocumentIssue(
            title="Partially Supported",
            description="Some evidence found",
            severity=SeverityEnum.MEDIUM,
            chunk_index=0,
        )
        chunk_content_map = {0: "Chunk content"}

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment.severity == CommentSeverity.MEDIUM
        assert comment.get_author() == "⚠️ Medium Priority"
        assert comment.get_initials() == "MP"

    def test_low_severity_uses_correct_author(self):
        issue = DocumentIssue(
            title="Minor Note",
            description="Just a suggestion",
            severity=SeverityEnum.LOW,
            chunk_index=0,
        )
        chunk_content_map = {0: "Chunk content"}

        comment = issue_to_comment(issue, chunk_content_map)

        assert comment.severity == CommentSeverity.LOW
        assert comment.get_author() == "💡 Low Priority"
        assert comment.get_initials() == "LP"


class TestBuildCitationSuggestionIssues:
    """Tests for the convert_citation_suggester_state_issues function"""

    @pytest.fixture
    def base_state(self) -> CitationSuggesterState:
        """Create a base state for testing"""
        return CitationSuggesterState(
            file=FileDocument(
                file_name="test.docx",
                file_path="/tmp/test.docx",
                file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                markdown="Test document content",
                markdown_token_count=10,
            ),
            config=CitationSuggesterWorkflowConfig(),
            chunks=[],
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
        assert issues[0].chunk_index == 0
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
