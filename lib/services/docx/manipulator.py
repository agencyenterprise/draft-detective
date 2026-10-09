"""DOCX manipulation service for adding AI-generated comments."""

import asyncio
import logging
import re
from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from docx import Document
from docx.document import Document as DocumentObject
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

from lib.config.env import config
from lib.models.issue import Issue
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.workflows.models import SeverityEnum
from lib.workflows.registry import get_workflow_manifest

logger = logging.getLogger(__name__)

# Matches characters illegal in XML 1.0: control chars except tab, newline, carriage return
_ILLEGAL_XML_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff\ufdd0-\ufdef\ufffe\uffff]"
)


def _sanitize_for_xml(text: str) -> str:
    """Remove characters that are illegal in XML 1.0."""
    return _ILLEGAL_XML_CHARS_RE.sub("", text)


class DocxManipulatorType(StrEnum):
    """Type of DOCX to generate."""

    COMMENTS = "comments"
    COMMENTS_WITH_LINKS = "comments-with-links"


# Severity mapping from workflow to DOCX
def _map_severity_enum_to_comment_severity(severity: SeverityEnum) -> "CommentSeverity":
    """Map workflow SeverityEnum to CommentSeverity."""
    mapping = {
        SeverityEnum.HIGH: CommentSeverity.HIGH,
        SeverityEnum.MEDIUM: CommentSeverity.MEDIUM,
        SeverityEnum.LOW: CommentSeverity.LOW,
        SeverityEnum.NONE: CommentSeverity.NONE,
    }
    return mapping.get(severity, CommentSeverity.NONE)


def _resolve_issue_line_range(issue: Issue) -> Optional[Tuple[int, int]]:
    """Return ``(start_line, end_line)`` for an issue, or None if it has none.

    Issues written before workflows moved to line ranges carry only
    `chunk_indices`, and the chunk data that used to translate those is gone with
    the chunk_splitting workflow. Such an issue cannot be anchored to a
    paragraph, so it is dropped from the export — see the caller, which logs it.
    """
    if issue.start_line is not None and issue.end_line is not None:
        return (issue.start_line, issue.end_line)
    return None


def count_unanchorable_issues(
    issues: Sequence[Issue], paragraph_line_ranges: Dict[int, Tuple[int, int]]
) -> Tuple[int, int]:
    """Count issues no export can place, split by cause.

    Returns ``(no_line_range, matched_no_paragraph)``. The export silently skips
    these — `issue_to_comment` applies the same two checks — so callers use this
    to report the omission instead of letting the export quietly come up short.
    """
    no_line_range = 0
    matched_no_paragraph = 0
    for issue in issues:
        line_range = _resolve_issue_line_range(issue)
        if line_range is None:
            no_line_range += 1
        elif (
            find_paragraph_by_line_range(
                paragraph_line_ranges, line_range[0], line_range[1]
            )
            is None
        ):
            matched_no_paragraph += 1
    return no_line_range, matched_no_paragraph


def _build_issue_anchor(line_range: Optional[Tuple[int, int]]) -> Optional[str]:
    """Build URL anchor fragment for a resolved issue line range (e.g. ``#L5-15``)."""
    if line_range is None:
        return None
    start, end = line_range
    return f"#L{start}-{end}"


class CommentSeverity(StrEnum):
    """Severity levels for DOCX comments."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Severity to author name and icon mapping
SEVERITY_AUTHORS = {
    CommentSeverity.HIGH: ("🚨 High Priority", "HP"),
    CommentSeverity.MEDIUM: ("⚠️ Medium Priority", "MP"),
    CommentSeverity.LOW: ("💡 Low Priority", "LP"),
    CommentSeverity.NONE: ("✅ Passing", "PA"),
}

class DocxComment(BaseModel):
    """Represents a comment to be added to a docx file."""

    paragraph_index: int
    comment_text: str
    severity: Optional[CommentSeverity] = None
    author: Optional[str] = None
    share_link: Optional[str] = None

    def get_author(self) -> str:
        """Get author name, derived from severity if not explicitly set."""
        if self.author:
            return self.author
        if self.severity:
            return SEVERITY_AUTHORS.get(
                self.severity, SEVERITY_AUTHORS[CommentSeverity.NONE]
            )[0]
        return "Draft Detective"

    def get_initials(self) -> str:
        """Get initials for the comment author."""
        if self.severity and not self.author:
            return SEVERITY_AUTHORS.get(
                self.severity, SEVERITY_AUTHORS[CommentSeverity.NONE]
            )[1]
        author = self.get_author()
        parts = author.split()
        text_parts = [
            p for p in parts if p.isalpha() or (len(p) > 1 and p[-1].isalpha())
        ]
        if len(text_parts) >= 2:
            return f"{text_parts[0][0]}{text_parts[1][0]}".upper()
        elif len(text_parts) == 1:
            return text_parts[0][:2].upper()
        return "AI"


def _get_workflow_display_name(issue: Issue) -> Optional[str]:
    """Resolve the human-readable workflow name for an issue."""
    manifest = get_workflow_manifest(issue.workflow_type, raise_exception=False)
    return manifest.name if manifest else None


def issue_to_comment(
    issue: Issue,
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
    share_token: Optional[str] = None,
    edit_notes: Sequence[str] = (),
) -> Optional["DocxComment"]:
    """Convert an Issue to DocxComment with optional share link.

    Resolves the issue to a paragraph by line-range overlap. Returns None when the
    issue has no resolvable line range or does not overlap any mapped paragraph.

    ``edit_notes`` are the issue's proposed-edit blocks, already formatted by
    `lib.services.docx.edit_notes`: what each edit changes, why, and whether it
    reached the document as a tracked change.
    """
    line_range = _resolve_issue_line_range(issue)
    if line_range is None:
        return None

    paragraph_index = find_paragraph_by_line_range(
        paragraph_line_ranges, line_range[0], line_range[1]
    )
    if paragraph_index is None:
        return None

    share_link = None
    if share_token:
        from lib.services.share_links import _build_share_url

        anchor = _build_issue_anchor(line_range)
        share_link = _build_share_url(share_token, anchor)

    workflow_name = _get_workflow_display_name(issue)
    title = f"{issue.title} ({workflow_name})" if workflow_name else issue.title

    # Include the suggested action and long_description (the "more details" content
    # shown in the UI) so the Word export carries the full context authors need —
    # e.g. for Reference Error Checker, which fields are wrong, the suggested action,
    # and the suggested updated reference.
    parts = [f"{title}\n\n{issue.description}"]
    if issue.suggested_action:
        parts.append(f"Suggested Action: {issue.suggested_action}")
    parts.extend(edit_notes)
    if issue.long_description:
        parts.append(issue.long_description)
    comment_text = "\n\n".join(parts)

    return DocxComment(
        paragraph_index=paragraph_index,
        comment_text=comment_text,
        severity=_map_severity_enum_to_comment_severity(issue.severity),
        share_link=share_link,
    )


class DocxManipulatorService:
    """Service for manipulating DOCX files with AI-generated comments."""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}

    def get_output_dir(self) -> Path:
        """The directory processed exports (and their scratch space) live in."""
        output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
        output_dir.mkdir(exist_ok=True)
        return output_dir

    def get_output_path(
        self, workflow_run_id: str, docx_type: DocxManipulatorType
    ) -> Path:
        """Get the deterministic output path for a processed docx file."""
        return self.get_output_dir() / f"{workflow_run_id}_{docx_type.value}.docx"

    async def add_comments_to_docx(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        docx_type: DocxManipulatorType = DocxManipulatorType.COMMENTS,
    ) -> str:
        """Add comments to a DOCX file at their resolved paragraph indices."""
        return await asyncio.to_thread(
            self._add_comments_to_docx_sync,
            original_docx_path,
            comments,
            workflow_run_id,
            docx_type,
        )

    def _add_comments_to_docx_sync(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        docx_type: DocxManipulatorType = DocxManipulatorType.COMMENTS,
    ) -> str:
        """Sync implementation for adding comments to DOCX."""
        original_path = Path(original_docx_path)

        if original_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"File must be .docx, got {original_path.suffix}")

        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_path = self.get_output_path(workflow_run_id, docx_type)
        logger.info(
            f"Creating reviewed docx at {output_path} with {len(comments)} comments"
        )

        doc = Document(original_docx_path)
        docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

        comments_added = 0
        comments_skipped = 0

        for comment in comments:
            para_idx = comment.paragraph_index

            if para_idx < 0 or para_idx >= len(docx_paragraphs):
                logger.warning(
                    f"Invalid paragraph index {para_idx} on comment, skipping"
                )
                comments_skipped += 1
                continue

            try:
                paragraph = docx_paragraphs[para_idx]
                full_comment_text = comment.comment_text
                if comment.share_link:
                    full_comment_text += (
                        f"\n\n🔗 View in Draft Detective: {comment.share_link}"
                    )

                self._add_comment_to_paragraph(
                    doc,
                    paragraph,
                    full_comment_text,
                    comment.get_author(),
                    comment.get_initials(),
                )
                comments_added += 1
            except Exception as e:
                logger.error(
                    f"Failed to add comment to paragraph {para_idx}: {e}", exc_info=True
                )
                comments_skipped += 1

        doc.save(str(output_path))
        logger.info(
            f"Created reviewed docx: {comments_added} added, {comments_skipped} skipped"
        )
        return str(output_path)

    def _add_comment_to_paragraph(
        self,
        doc: DocumentObject,
        paragraph: Paragraph,
        comment_text: str,
        author: str,
        initials: str,
    ):
        """Add a comment to a paragraph."""
        try:
            doc.add_comment(
                runs=paragraph.runs if paragraph.runs else [paragraph.add_run("")],
                text=_sanitize_for_xml(comment_text),
                author=_sanitize_for_xml(author),
                initials=_sanitize_for_xml(initials),
            )
        except AttributeError as e:
            logger.warning(f"Error inserting comment to docx: {e}")
            raise


docx_manipulator_service = DocxManipulatorService()
