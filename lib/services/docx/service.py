"""Generate exported DOCX files (with comments and tracked changes) on demand."""

import logging
import uuid
from typing import Literal

from lib.models.workflow_run import WorkflowRunType
from lib.services.docx.edit_export import (
    EditExport,
    describe_edit_export,
    plan_edit_export,
    write_edit_export,
)
from lib.services.docx.legacy_doc import readable_docx
from lib.services.docx.manipulator import (
    DocxManipulatorType,
    count_unanchorable_issues,
    docx_manipulator_service,
    issue_to_comment,
)
from lib.services.docx.paragraph_line_mapper import build_paragraph_line_ranges
from lib.services.file_artifacts_service.file_artifacts_service import (
    FileArtifactsService,
)
from lib.services.issue_persistence import get_project_issues
from lib.services.projects.service import get_project_by_id
from lib.workflows.models import SeverityEnum

logger = logging.getLogger(__name__)


def _resolved_revision(requested: int | None, current: int) -> int:
    """The revision to export, defaulting to the project's current one.

    A revision the project does not have is refused rather than silently
    served as the current one: the caller asked for a specific document, and
    the issues and counts it is paired with belong to that revision.
    """
    if requested is None:
        return current
    if requested < 1 or requested > current:
        raise ValueError(
            f"Revision {requested} does not exist for this project "
            f"(it has revisions 1 to {current})"
        )
    return requested


async def generate_docx(
    project_id: str,
    share_token: str | None,
    severities: list[SeverityEnum] | None = None,
    workflow_types: list[WorkflowRunType] | None = None,
    docx_type: DocxManipulatorType | Literal["original"] = DocxManipulatorType.COMMENTS,
    include_passing: bool = False,
    include_edits: bool = True,
    revision: int | None = None,
) -> tuple[str, str]:
    """Generate an export of the project's DOCX.

    Always regenerates from scratch — there is no caching layer.

    Args:
        project_id: The project ID
        share_token: Optional share token for share links in comments
        severities: Optional list of severity levels to filter issues
        workflow_types: Optional list of workflow types to filter issues
        docx_type: The export variant. ``"original"`` returns the uploaded file
            untouched; ``COMMENTS`` / ``COMMENTS_WITH_LINKS`` produce the
            corresponding processed variants.
        include_passing: Whether to include passing issues (severity=none)
        include_edits: Whether to apply the issues' proposed edits as Word
            tracked changes, on top of the comments. Comment exports only.
            Every edit is described in its issue's comment either way.
        revision: Which revision of the main document to export. Defaults to
            the project's current revision. The app can have an earlier
            revision open, and the file, the issues and the counts the user was
            shown all have to come from the same one.

    Returns:
        ``(file_path, filename)`` for the generated file.
    """
    project = await get_project_by_id(project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    revision = _resolved_revision(revision, project.current_revision)

    file_artifacts = FileArtifactsService(project_id, revision=revision)
    # Asked for by name, not left to the service's default: without an explicit
    # revision `get_main_file` falls back to the document-processing state when
    # the row has no cached markdown, and that state is always the *current*
    # revision. A historical export would then pair this revision's issues with
    # the current revision's file.
    main_file = await file_artifacts.get_main_file(revision=revision)

    if docx_type == "original":
        logger.info(f"Serving original DOCX for {project_id}")
        return main_file.file_path, main_file.file_name

    # After the "original" early-return above, docx_type is a DocxManipulatorType.
    assert isinstance(docx_type, DocxManipulatorType)

    # Validate file is a DOCX
    main_file_path = main_file.file_path.lower()
    if not main_file_path.endswith(".docx") and not main_file_path.endswith(".doc"):
        raise ValueError("Main file must be a .docx or .doc to generate reviewed DOCX")

    # A Word 97 binary is read through the LibreOffice conversion ingestion
    # made its markdown from; the output is a .docx either way.
    async with readable_docx(main_file) as docx_path:
        # Build paragraph → (start_line, end_line) map via marker injection. This is
        # authoritative (no fuzzy matching) and resolves each issue's line range to a
        # target docx paragraph. The persisted
        # markdown's line count guards against a structurally different conversion
        # (e.g. drawing rasterization failing now but not at ingestion) silently
        # anchoring every comment to the wrong paragraph.
        paragraph_line_ranges = await build_paragraph_line_ranges(
            docx_path,
            expected_line_count=(
                main_file.markdown.count("\n") + 1 if main_file.markdown else None
            ),
        )

        # Query persisted issues directly from DB (faster than computing from workflow states)
        # get_project_issues excludes archived issues
        all_issues = list(
            await get_project_issues(
                project_id=uuid.UUID(project_id),
                revision=revision,
                workflow_types=workflow_types,
            )
        )

        # Exclude resolved issues from export
        issues = [issue for issue in all_issues if not issue.is_resolved]

        # Filter issues by severity if specified
        if severities:
            issues = [issue for issue in issues if issue.severity in severities]

        # Exclude passing issues (severity=none) unless explicitly included
        if not include_passing:
            issues = [issue for issue in issues if issue.severity != SeverityEnum.NONE]

        if not share_token:
            docx_type = DocxManipulatorType.COMMENTS

        # The export silently skips issues it cannot tie to a paragraph, so account
        # for them here. Two causes: no
        # line range at all (typically a legacy row carrying only chunk_indices, from
        # before workflows emitted line ranges), or a range overlapping no paragraph.
        no_range, unmatched = count_unanchorable_issues(issues, paragraph_line_ranges)
        if no_range or unmatched:
            logger.warning(
                "DOCX export (%s) for project %s omits %d of %d issues that cannot be "
                "anchored to a paragraph: %d have no line range, %d have one that "
                "matches no paragraph",
                docx_type.value,
                project_id,
                no_range + unmatched,
                len(issues),
                no_range,
                unmatched,
            )

        if docx_type in [
            DocxManipulatorType.COMMENTS,
            DocxManipulatorType.COMMENTS_WITH_LINKS,
        ]:
            share_token_for_comments = (
                share_token
                if docx_type == DocxManipulatorType.COMMENTS_WITH_LINKS
                else None
            )
            historical = revision != project.current_revision
            if share_token_for_comments is not None and historical:
                # A share link opens whatever the shared page shows, and that page
                # has no revision of its own to open -- it shows the current one.
                # A link written into a historical export would therefore send the
                # reader to a different document than the comment beside it.
                logger.info(
                    "DOCX export for project %s omits share links: it covers revision "
                    "%d, and the shared page shows revision %d",
                    project_id,
                    revision,
                    project.current_revision,
                )
                share_token_for_comments = None
            workspace_root = str(docx_manipulator_service.get_output_dir())
            comment_type = docx_type

            async def write_comments(edit_export: EditExport) -> str:
                # A fresh output id per call, so concurrent exports never collide
                # and an export written twice never reuses its first file.
                comments = [
                    c
                    for issue in issues
                    if (
                        c := issue_to_comment(
                            issue,
                            paragraph_line_ranges,
                            share_token_for_comments,
                            edit_notes=edit_export.notes_for(issue.id),
                            show_severity=project.group_by_severity,
                        )
                    )
                ]
                return await docx_manipulator_service.add_comments_to_docx(
                    original_docx_path=docx_path,
                    comments=comments,
                    workflow_run_id=uuid.uuid4().hex,
                    docx_type=comment_type,
                )

            if include_edits:
                edit_export = await plan_edit_export(
                    issues=issues,
                    markdown=main_file.markdown or "",
                    docx_path=docx_path,
                    paragraph_line_ranges=paragraph_line_ranges,
                    workspace_root=workspace_root,
                )
                # Comments first, then redlines: once the redlines are in, the
                # paragraph index map no longer describes the file, since
                # python-docx stops reading inserted and deleted runs as
                # paragraph text.
                output_path = await write_edit_export(
                    issues,
                    edit_export,
                    write_comments,
                    project_id,
                    workspace_root=workspace_root,
                )
            else:
                # Comments only: the edits are still described, nothing is written.
                output_path = await write_comments(describe_edit_export(issues))
        else:
            raise ValueError(f"Unsupported docx_type: {docx_type}")

    base_name = main_file.file_name.rsplit(".", 1)[0]
    filename = f"{base_name}_{docx_type.value}.docx"
    return output_path, filename
