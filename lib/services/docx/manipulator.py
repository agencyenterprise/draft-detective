"""DOCX manipulation service for adding AI-generated comments."""

import asyncio
import json
import logging
import re
from collections import defaultdict
from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from docx import Document
from docx.document import Document as DocumentObject
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

from lib.config.env import config
from lib.models.issue import Issue
from lib.services.chunk_line_matcher import (
    IndexedChunkWithLines,
    find_line_range_by_chunks,
)
from lib.services.docx.paragraph_line_mapper import find_paragraph_by_line_range
from lib.services.docx.docx_xml import (
    add_custom_properties_to_docx,
    wrap_paragraph_with_content_control,
)
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

    ADD_IN = "add-in"
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


def _resolve_issue_line_range(
    issue: Issue, chunks: Sequence[IndexedChunkWithLines]
) -> Optional[Tuple[int, int]]:
    """Return ``(start_line, end_line)`` for an issue, or None if unresolvable.

    Prefers native line-range fields. Falls back to deriving the range from legacy
    ``chunk_indices`` using the provided chunks so the export pipeline downstream
    can always reason in line-range terms.
    """
    if issue.start_line is not None and issue.end_line is not None:
        return (issue.start_line, issue.end_line)
    if issue.chunk_indices:
        return find_line_range_by_chunks(chunks, issue.chunk_indices)
    return None


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

ISSUE_MARKER_TAG = "AIReviewer_Issue_Marker"
PARAGRAPH_LINE_RANGES_PROPERTY = "AIReviewer_ParagraphLineRanges"

SEVERITY_HIGHLIGHT_COLORS = {
    SeverityEnum.HIGH: "F87274",
    SeverityEnum.MEDIUM: "CD8900",
    SeverityEnum.LOW: "52AEFF",
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
    chunks: Sequence[IndexedChunkWithLines],
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
    share_token: Optional[str] = None,
) -> Optional["DocxComment"]:
    """Convert an Issue to DocxComment with optional share link.

    Resolves the issue to a paragraph by line-range overlap. Returns None when the
    issue has no resolvable line range or does not overlap any mapped paragraph.
    """
    line_range = _resolve_issue_line_range(issue, chunks)
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

    return DocxComment(
        paragraph_index=paragraph_index,
        comment_text=f"{title}\n\n{issue.description}",
        severity=_map_severity_enum_to_comment_severity(issue.severity),
        share_link=share_link,
    )


def _build_issue_map(
    issues: List[Issue],
    chunks: Sequence[IndexedChunkWithLines],
    paragraph_line_ranges: Dict[int, Tuple[int, int]],
) -> Dict[int, List[Issue]]:
    issue_map: Dict[int, List[Issue]] = defaultdict(list)
    for issue in issues:
        line_range = _resolve_issue_line_range(issue, chunks)
        if line_range is None:
            continue
        paragraph_index = find_paragraph_by_line_range(
            paragraph_line_ranges, line_range[0], line_range[1]
        )
        if paragraph_index is None:
            continue
        issues_for_paragraph = issue_map[paragraph_index]
        existing_hashes = {i.issue_hash for i in issues_for_paragraph}
        if issue.issue_hash not in existing_hashes:
            issues_for_paragraph.append(issue)
    return issue_map


def _get_paragraph_severity(issues: List[Issue]) -> SeverityEnum:
    if not issues:
        return SeverityEnum.NONE
    return max(issues, key=lambda issue: issue.severity.sort_index()).severity


class DocxManipulatorService:
    """Service for manipulating DOCX files with AI-generated comments."""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}

    def get_output_path(
        self, workflow_run_id: str, docx_type: DocxManipulatorType
    ) -> Path:
        """Get the deterministic output path for a processed docx file."""
        output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
        output_dir.mkdir(exist_ok=True)
        return output_dir / f"{workflow_run_id}_{docx_type.value}.docx"

    async def add_addin_metadata_to_docx(
        self,
        original_docx_path: str,
        share_token: str,
        workflow_run_id: str,
        paragraph_line_ranges: Dict[int, Tuple[int, int]],
        chunks: Sequence[IndexedChunkWithLines] | None = None,
        issues: List[Issue] | None = None,
    ) -> str:
        """Add custom properties and a comment to a DOCX file.

        ``chunks`` are only consulted as a legacy fallback for resolving
        pre-migration issues that lack ``start_line``/``end_line``.
        """
        return await asyncio.to_thread(
            self._add_addin_metadata_to_docx_sync,
            original_docx_path,
            share_token,
            workflow_run_id,
            paragraph_line_ranges,
            chunks,
            issues,
        )

    def _add_addin_metadata_to_docx_sync(
        self,
        original_docx_path: str,
        share_token: str,
        workflow_run_id: str,
        paragraph_line_ranges: Dict[int, Tuple[int, int]],
        chunks: Sequence[IndexedChunkWithLines] | None = None,
        issues: List[Issue] | None = None,
    ) -> str:
        """Sync implementation for add-in metadata generation."""
        original_path = Path(original_docx_path)
        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_path = self.get_output_path(workflow_run_id, DocxManipulatorType.ADD_IN)
        logger.info(f"Creating reviewed docx at {output_path} with add-in metadata")

        doc = Document(original_docx_path)
        docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

        # Create the content controls for each paragraph that has issues
        if issues is not None:
            if paragraph_line_ranges:
                issue_map = _build_issue_map(
                    issues, chunks or [], paragraph_line_ranges
                )
                for paragraph_index, paragraph in enumerate(docx_paragraphs):
                    paragraph_issues = issue_map.get(paragraph_index, [])
                    if not paragraph_issues:
                        continue
                    paragraph_severity = _get_paragraph_severity(paragraph_issues)
                    highlight_color = SEVERITY_HIGHLIGHT_COLORS.get(paragraph_severity)
                    wrap_paragraph_with_content_control(
                        paragraph=paragraph,
                        tag_value=f"{ISSUE_MARKER_TAG}:{paragraph_index}",
                        title=f"{len(paragraph_issues)} Draft Detective Issues",
                        color_hex=highlight_color,
                    )
            else:
                logger.warning(
                    "Issue markers skipped: missing paragraph line-range mapping"
                )

        doc.save(str(output_path))
        add_custom_properties_to_docx(
            output_path,
            {
                "AIReviewer_AuthToken": share_token,
                PARAGRAPH_LINE_RANGES_PROPERTY: (
                    json.dumps(
                        {str(p): [s, e] for p, (s, e) in paragraph_line_ranges.items()}
                    )
                    if paragraph_line_ranges
                    else None
                ),
            },
        )
        return str(output_path)

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
