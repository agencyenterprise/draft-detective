"""Tests for DOCX generation helper functions"""

import contextlib
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.issue import Issue
from lib.services.docx.manipulator import (
    CommentSeverity,
    DocxComment,
    DocxManipulatorType,
    count_unanchorable_issues,
    issue_to_comment,
)
from lib.services.docx.edit_export import EditExport
from lib.services.docx_workflow_service import _resolved_revision, generate_docx
from lib.workflows.models import DocumentIssue, SeverityEnum, WorkflowRunType

_SERVICE = "lib.services.docx_workflow_service"

_FAKE_PROJECT_ID = uuid.uuid4()
_FAKE_WORKFLOW_RUN_ID = uuid.uuid4()


def _make_issue(
    title: str,
    description: str,
    severity: SeverityEnum,
    workflow_type: WorkflowRunType,
    chunk_indices: list[int] | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    long_description: str | None = None,
    suggested_action: str | None = None,
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
        long_description=long_description,
        suggested_action=suggested_action,
        severity=severity,
        workflow_type=workflow_type,
        chunk_indices=chunk_indices,
        start_line=start_line,
        end_line=end_line,
        created_at=now,
        updated_at=now,
    )


class TestIssueToComment:
    """Tests for the issue_to_comment function"""

    def test_converts_issue_to_comment_successfully(self):
        issue = _make_issue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=3,
        )
        paragraph_line_ranges = {0: (1, 3)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment is not None
        assert isinstance(comment, DocxComment)
        assert comment.paragraph_index == 0
        assert "Unsupported Claim" in comment.comment_text
        assert "This claim lacks evidence" in comment.comment_text
        assert comment.severity == CommentSeverity.HIGH
        assert comment.get_author() == "🚨 High Priority"

    def test_includes_suggested_action_and_long_description_in_order(self):
        """Comment carries description, then suggested action, then long_description."""
        issue = _make_issue(
            title="Reference has incorrect fields",
            description="The publication year does not match public sources.",
            suggested_action="Update the year to 2021.",
            long_description="### Field validations\n\n- **Year**: 2019 → 2021",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=3,
        )
        paragraph_line_ranges = {0: (1, 3)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment is not None
        text = comment.comment_text
        assert "Suggested Action: Update the year to 2021." in text
        assert "### Field validations" in text
        assert "2019 → 2021" in text
        # Order: description → suggested action → long_description
        assert (
            text.index("does not match public sources")
            < text.index("Suggested Action:")
            < text.index("### Field validations")
        )

    def test_edit_notes_sit_between_the_suggested_action_and_the_details(self):
        """Proposed edits read after the action they carry out."""
        issue = _make_issue(
            title="Reference has incorrect fields",
            description="The publication year does not match public sources.",
            suggested_action="Update the year to 2021.",
            long_description="### Field validations",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=3,
        )

        comment = issue_to_comment(
            issue,
            {0: (1, 3)},
            edit_notes=[
                'Proposed edit: "2019" → "2021"\nthe year is wrong\n'
                "Applied below as a tracked change."
            ],
        )

        assert comment is not None
        text = comment.comment_text
        assert "Applied below as a tracked change." in text
        assert (
            text.index("Suggested Action:")
            < text.index("Proposed edit:")
            < text.index("### Field validations")
        )

    def test_a_comment_without_edit_notes_is_unchanged(self):
        issue = _make_issue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            suggested_action="Cite a source.",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=3,
        )

        comment = issue_to_comment(issue, {0: (1, 3)}, edit_notes=[])

        assert comment is not None
        assert comment.comment_text.endswith("Suggested Action: Cite a source.")

    def test_omits_long_description_when_absent(self):
        """No trailing separator/content when long_description is None."""
        issue = _make_issue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=3,
        )
        paragraph_line_ranges = {0: (1, 3)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment is not None
        assert comment.comment_text.endswith("This claim lacks evidence")

    def test_legacy_chunk_indices_issue_is_dropped(self):
        """An issue carrying only chunk_indices can no longer be placed.

        Those rows pre-date workflows emitting line ranges, and the chunk data
        that used to translate them went with the chunk_splitting workflow. The
        export drops them rather than guessing at a paragraph; the caller logs
        how many were omitted.
        """
        issue = _make_issue(
            title="Legacy issue",
            description="Only has chunk_indices",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            chunk_indices=[1],
        )
        paragraph_line_ranges = {0: (1, 2), 1: (3, 5)}

        assert issue_to_comment(issue, paragraph_line_ranges) is None

    def test_returns_none_when_line_range_unresolvable(self):
        issue = _make_issue(
            title="Invalid reference",
            description="Reference not found",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.REFERENCE_VALIDATION_V2,
        )

        comment = issue_to_comment(issue, {})

        assert comment is None

    def test_returns_none_when_no_paragraph_overlaps(self):
        issue = _make_issue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=100,
            end_line=110,
        )
        paragraph_line_ranges = {0: (1, 10), 1: (11, 20)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment is None

    def test_share_link_anchor_uses_line_range(self):
        issue = _make_issue(
            title="Some issue",
            description="Issue description",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=5,
            end_line=15,
        )
        paragraph_line_ranges = {0: (1, 20)}

        comment = issue_to_comment(
            issue, paragraph_line_ranges, share_token="share-token-abc"
        )

        assert comment is not None
        assert comment.share_link is not None
        assert comment.share_link.endswith("#L5-15")

    def test_medium_severity_uses_correct_author(self):
        issue = _make_issue(
            title="Partially Supported",
            description="Some evidence found",
            severity=SeverityEnum.MEDIUM,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=1,
        )
        paragraph_line_ranges = {0: (1, 1)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment.severity == CommentSeverity.MEDIUM
        assert comment.get_author() == "⚠️ Medium Priority"
        assert comment.get_initials() == "MP"

    def test_low_severity_uses_correct_author(self):
        issue = _make_issue(
            title="Minor Note",
            description="Just a suggestion",
            severity=SeverityEnum.LOW,
            workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
            start_line=1,
            end_line=1,
        )
        paragraph_line_ranges = {0: (1, 1)}

        comment = issue_to_comment(issue, paragraph_line_ranges)

        assert comment.severity == CommentSeverity.LOW
        assert comment.get_author() == "💡 Low Priority"
        assert comment.get_initials() == "LP"


class TestUnanchorableIssueAccounting:
    """The count must match what the export paths actually drop.

    Both modes skip issues they cannot tie to a paragraph — `issue_to_comment`
    for comments, `_build_issue_map` for the add-in — and both do it silently.
    The count is what turns that into a log line, so it has to agree with the
    real behaviour rather than approximate it.
    """

    PARAGRAPHS = {0: (1, 2), 1: (3, 5)}

    def _mixed_issues(self):
        return [
            _make_issue(  # anchors
                title="anchored",
                description="d",
                severity=SeverityEnum.LOW,
                workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
                start_line=3,
                end_line=5,
            ),
            _make_issue(  # legacy: chunk_indices only
                title="legacy",
                description="d",
                severity=SeverityEnum.LOW,
                workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
                chunk_indices=[1],
            ),
            _make_issue(  # no location at all
                title="locationless",
                description="d",
                severity=SeverityEnum.LOW,
                workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
            ),
            _make_issue(  # has a range, but no paragraph covers it
                title="off the end",
                description="d",
                severity=SeverityEnum.LOW,
                workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
                start_line=90,
                end_line=95,
            ),
        ]

    def test_counts_are_split_by_cause(self):
        no_range, unmatched = count_unanchorable_issues(
            self._mixed_issues(), self.PARAGRAPHS
        )

        assert (no_range, unmatched) == (2, 1)

    def test_total_matches_what_the_comments_path_drops(self):
        issues = self._mixed_issues()
        comments = [c for i in issues if (c := issue_to_comment(i, self.PARAGRAPHS))]

        no_range, unmatched = count_unanchorable_issues(issues, self.PARAGRAPHS)

        assert no_range + unmatched == len(issues) - len(comments)

    def test_nothing_is_counted_when_every_issue_anchors(self):
        issues = [
            _make_issue(
                title="a",
                description="d",
                severity=SeverityEnum.LOW,
                workflow_type=WorkflowRunType.RECOMMENDATION_CHECK,
                start_line=1,
                end_line=2,
            )
        ]

        assert count_unanchorable_issues(issues, self.PARAGRAPHS) == (0, 0)


class TestGenerateDocxRevision:
    """The export follows the revision it was asked for, not just the latest."""

    @staticmethod
    def _patches(tmp_path, current_revision: int = 3, issues=()):
        """Everything `generate_docx` reaches for, stubbed.

        Only the routing matters here -- which revision the file lookup and the
        issue query are given, and what the comments are told -- so the
        manipulator, the file artifacts and the comment builder are stubs.
        """
        project = SimpleNamespace(current_revision=current_revision)
        main_file = SimpleNamespace(
            file_path=str(tmp_path / "main.docx"),
            file_name="main.docx",
            markdown="Output increased by 14%.",
        )
        artifacts = MagicMock()
        artifacts.get_main_file = AsyncMock(return_value=main_file)
        manipulator = MagicMock()
        manipulator.get_output_dir = MagicMock(return_value=tmp_path)
        manipulator.add_comments_to_docx = AsyncMock(
            return_value=str(tmp_path / "out.docx")
        )
        return contextlib.ExitStack(), {
            "_get_project_by_id": patch(
                f"{_SERVICE}._get_project_by_id", AsyncMock(return_value=project)
            ),
            "FileArtifactsService": patch(
                f"{_SERVICE}.FileArtifactsService", MagicMock(return_value=artifacts)
            ),
            "build_paragraph_line_ranges": patch(
                f"{_SERVICE}.build_paragraph_line_ranges",
                AsyncMock(return_value={0: (1, 1)}),
            ),
            "get_project_issues": patch(
                f"{_SERVICE}.get_project_issues", AsyncMock(return_value=list(issues))
            ),
            "issue_to_comment": patch(
                f"{_SERVICE}.issue_to_comment", MagicMock(return_value=None)
            ),
            "docx_manipulator_service": patch(
                f"{_SERVICE}.docx_manipulator_service", manipulator
            ),
        }

    async def _generate(self, tmp_path, **kwargs):
        stack, patches = self._patches(
            tmp_path,
            kwargs.pop("current_revision", 3),
            kwargs.pop("issues", ()),
        )
        with stack:
            entered = {name: stack.enter_context(p) for name, p in patches.items()}
            path, _ = await generate_docx(
                project_id=str(_FAKE_PROJECT_ID),
                share_token=kwargs.pop("share_token", None),
                docx_type=kwargs.pop("docx_type", DocxManipulatorType.COMMENTS),
                **kwargs,
            )
        return path, entered

    @pytest.mark.asyncio
    async def test_the_requested_revision_reaches_the_file_and_the_issues(
        self, tmp_path
    ):
        _, mocks = await self._generate(tmp_path, revision=2)

        assert mocks["FileArtifactsService"].call_args.kwargs["revision"] == 2
        assert mocks["get_project_issues"].await_args.kwargs["revision"] == 2

    @pytest.mark.asyncio
    async def test_no_revision_means_the_projects_current_one(self, tmp_path):
        _, mocks = await self._generate(tmp_path)

        assert mocks["FileArtifactsService"].call_args.kwargs["revision"] == 3
        assert mocks["get_project_issues"].await_args.kwargs["revision"] == 3

    @pytest.mark.asyncio
    async def test_the_file_lookup_is_told_the_revision_by_name(self, tmp_path):
        # Not left to the service's default: without an explicit revision the
        # lookup falls back to the document-processing state when the row has
        # no cached markdown, and that state is always the current revision --
        # so a historical export would serve the current revision's file.
        _, mocks = await self._generate(tmp_path, revision=1)
        artifacts = mocks["FileArtifactsService"].return_value

        assert artifacts.get_main_file.await_args.kwargs == {"revision": 1}

    @pytest.mark.asyncio
    async def test_the_file_lookup_defaults_to_the_projects_current_revision(
        self, tmp_path
    ):
        _, mocks = await self._generate(tmp_path)
        artifacts = mocks["FileArtifactsService"].return_value

        assert artifacts.get_main_file.await_args.kwargs == {"revision": 3}

    @pytest.mark.asyncio
    async def test_a_revision_the_project_does_not_have_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            await self._generate(tmp_path, revision=4)
        with pytest.raises(ValueError, match="does not exist"):
            await self._generate(tmp_path, revision=0)


class TestShareLinksInAHistoricalExport:
    """A share link opens the current revision, so an old export gets none."""

    @staticmethod
    def _issue():
        return _make_issue(
            title="Unsupported Claim",
            description="This claim lacks evidence",
            severity=SeverityEnum.HIGH,
            workflow_type=WorkflowRunType.CLAIM_REFERENCE_VALIDATION_V2,
            start_line=1,
            end_line=1,
        )

    async def _share_token_used(self, tmp_path, **kwargs):
        _, mocks = await TestGenerateDocxRevision()._generate(
            tmp_path,
            issues=[self._issue()],
            share_token="tok",
            docx_type=DocxManipulatorType.COMMENTS_WITH_LINKS,
            include_edits=False,
            **kwargs,
        )
        (call,) = mocks["issue_to_comment"].call_args_list
        return call.args[2]

    @pytest.mark.asyncio
    async def test_an_earlier_revision_gets_comments_without_links(self, tmp_path):
        assert (
            await self._share_token_used(tmp_path, current_revision=2, revision=1)
            is None
        )

    @pytest.mark.asyncio
    async def test_the_current_revision_still_gets_its_links(self, tmp_path):
        assert (
            await self._share_token_used(tmp_path, current_revision=2, revision=2)
            == "tok"
        )
        assert await self._share_token_used(tmp_path, current_revision=2) == "tok"


class TestGenerateDocxWithoutTrackedChanges:
    @pytest.mark.asyncio
    async def test_comments_only_plans_nothing_and_writes_no_redlines(self, tmp_path):
        stack, patches = TestGenerateDocxRevision._patches(tmp_path)
        plan = AsyncMock()
        apply = AsyncMock()
        with stack:
            for one in patches.values():
                stack.enter_context(one)
            stack.enter_context(patch(f"{_SERVICE}.plan_edit_export", plan))
            stack.enter_context(patch(f"{_SERVICE}.apply_edit_export", apply))
            await generate_docx(
                project_id=str(_FAKE_PROJECT_ID),
                share_token=None,
                docx_type=DocxManipulatorType.COMMENTS,
                include_edits=False,
            )

        plan.assert_not_awaited()
        apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_with_tracked_changes_both_passes_run(self, tmp_path):
        stack, patches = TestGenerateDocxRevision._patches(tmp_path)
        plan = AsyncMock(return_value=EditExport())
        apply = AsyncMock()
        with stack:
            for one in patches.values():
                stack.enter_context(one)
            stack.enter_context(patch(f"{_SERVICE}.plan_edit_export", plan))
            stack.enter_context(patch(f"{_SERVICE}.apply_edit_export", apply))
            await generate_docx(
                project_id=str(_FAKE_PROJECT_ID),
                share_token=None,
                docx_type=DocxManipulatorType.COMMENTS,
                include_edits=True,
            )

        plan.assert_awaited_once()
        apply.assert_awaited_once()


class TestResolvedRevision:
    def test_none_falls_back_to_the_current_revision(self):
        assert _resolved_revision(None, 3) == 3

    def test_a_revision_the_project_has_is_kept(self):
        assert _resolved_revision(1, 3) == 1
        assert _resolved_revision(3, 3) == 3

    def test_anything_outside_the_range_is_refused(self):
        with pytest.raises(ValueError, match="revisions 1 to 3"):
            _resolved_revision(4, 3)
        with pytest.raises(ValueError, match="revisions 1 to 3"):
            _resolved_revision(0, 3)
