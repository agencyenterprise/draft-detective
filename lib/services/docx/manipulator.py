"""DOCX manipulation service for adding AI-generated comments."""

import asyncio
from collections import defaultdict
import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from docx.document import Document as DocumentObject
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

from lib.config.env import config
from lib.services.docx.chunk_mapper import ChunkLike, create_chunk_to_paragraph_mapping
from lib.services.docx.docx_xml import (
    add_custom_properties_to_docx,
    wrap_paragraph_with_content_control,
)
from lib.workflows.models import DocumentIssue, SeverityEnum

logger = logging.getLogger(__name__)


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


def _build_issue_anchor(issue: DocumentIssue) -> Optional[str]:
    """Build URL anchor fragment for an issue."""
    if issue.chunk_index is not None:
        return f"#chunk-{issue.chunk_index}"
    return None


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
    CommentSeverity.NONE: ("📝 Note", "NT"),
}

ISSUE_MARKER_TAG = "AIReviewer_Issue_Marker"

SEVERITY_HIGHLIGHT_COLORS = {
    SeverityEnum.HIGH: "F87274",
    SeverityEnum.MEDIUM: "CD8900",
    SeverityEnum.LOW: "52AEFF",
}


class DocxComment(BaseModel):
    """Represents a comment to be added to a docx file."""

    chunk_index: int
    text: str
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
        return "AI Reviewer"

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


def issue_to_comment(
    issue: DocumentIssue,
    chunk_content_map: Dict[int, str],
    share_token: Optional[str] = None,
) -> Optional["DocxComment"]:
    """Convert DocumentIssue to DocxComment with optional share link."""
    if issue.chunk_index is None:
        return None

    chunk_content = chunk_content_map.get(issue.chunk_index)
    if not chunk_content:
        return None

    share_link = None
    if share_token:
        from lib.services.share_links import _build_share_url

        anchor = _build_issue_anchor(issue)
        share_link = _build_share_url(share_token, anchor)

    return DocxComment(
        chunk_index=issue.chunk_index,
        text=chunk_content,
        comment_text=f"{issue.title}\n\n{issue.description}",
        severity=_map_severity_enum_to_comment_severity(issue.severity),
        share_link=share_link,
    )


def _build_issue_map(
    issues: List[DocumentIssue],
    chunk_to_paragraph_mapping: Dict[int, int],
) -> Dict[int, List[DocumentIssue]]:
    issue_map: Dict[int, List[DocumentIssue]] = defaultdict[int, List[DocumentIssue]](
        list
    )
    for issue in issues:
        indices_to_process = set()
        if issue.chunk_index is not None:
            indices_to_process.add(issue.chunk_index)
        if issue.chunk_indices:
            indices_to_process.update(issue.chunk_indices)
        for chunk_index in indices_to_process:
            paragraph_index = chunk_to_paragraph_mapping.get(chunk_index)
            if paragraph_index is None:
                continue
            issues_for_paragraph = issue_map[paragraph_index]
            if issue.id not in [i.id for i in issues_for_paragraph]:
                issues_for_paragraph.append(issue)
    return issue_map


def _get_paragraph_severity(issues: List[DocumentIssue]) -> SeverityEnum:
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
        chunks: List[ChunkLike] | None = None,
        issues: List[DocumentIssue] | None = None,
    ) -> str:
        """Add custom properties and a comment to a DOCX file."""
        return await asyncio.to_thread(
            self._add_addin_metadata_to_docx_sync,
            original_docx_path,
            share_token,
            workflow_run_id,
            chunks,
            issues,
        )

    def _add_addin_metadata_to_docx_sync(
        self,
        original_docx_path: str,
        share_token: str,
        workflow_run_id: str,
        chunks: List[ChunkLike] | None = None,
        issues: List[DocumentIssue] | None = None,
    ) -> str:
        """Sync implementation for add-in metadata generation."""
        original_path = Path(original_docx_path)
        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_path = self.get_output_path(workflow_run_id, DocxManipulatorType.ADD_IN)
        logger.info(f"Creating reviewed docx at {output_path} with add-in metadata")

        doc = Document(original_docx_path)
        docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

        chunk_to_para_mapping = {}
        if chunks:
            chunk_to_para_mapping = create_chunk_to_paragraph_mapping(
                chunks, docx_paragraphs
            )
        # Create the content controls to each paragraph that has issues
        if issues is not None:
            if chunk_to_para_mapping:
                issue_map = _build_issue_map(issues, chunk_to_para_mapping)
                for paragraph_index, paragraph in enumerate(docx_paragraphs):
                    paragraph_issues = issue_map.get(paragraph_index, [])
                    if not paragraph_issues:
                        continue
                    paragraph_severity = _get_paragraph_severity(paragraph_issues)
                    highlight_color = SEVERITY_HIGHLIGHT_COLORS.get(paragraph_severity)
                    wrap_paragraph_with_content_control(
                        paragraph=paragraph,
                        tag_value=f"{ISSUE_MARKER_TAG}:{paragraph_index}",
                        title=f"{len(paragraph_issues)} AI Reviewer Issues",
                        color_hex=highlight_color,
                    )
            else:
                logger.warning(
                    "Issue markers skipped: missing chunk-to-paragraph mapping"
                )

        doc.save(str(output_path))
        add_custom_properties_to_docx(
            output_path,
            {
                "AIReviewer_AuthToken": share_token,
                "AIReviewer_ChunkToParagraphMapping": (
                    json.dumps(chunk_to_para_mapping) if chunk_to_para_mapping else None
                ),
            },
        )
        return str(output_path)

    async def add_comments_to_docx(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        chunks: List[ChunkLike] | None = None,
        docx_type: DocxManipulatorType = DocxManipulatorType.COMMENTS,
    ) -> str:
        """Add comments to a DOCX file based on chunk indices."""
        return await asyncio.to_thread(
            self._add_comments_to_docx_sync,
            original_docx_path,
            comments,
            workflow_run_id,
            chunks,
            docx_type,
        )

    def _add_comments_to_docx_sync(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        chunks: List[ChunkLike] | None = None,
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

        chunk_to_para_mapping = {}
        if chunks:
            chunk_to_para_mapping = create_chunk_to_paragraph_mapping(
                chunks, docx_paragraphs
            )
        else:
            logger.warning("No chunks provided, comments will not be added")

        comments_added = 0
        comments_skipped = 0

        for comment in comments:
            para_idx = chunk_to_para_mapping.get(comment.chunk_index)

            if para_idx is None:
                logger.warning(
                    f"No paragraph mapping for chunk {comment.chunk_index}, skipping"
                )
                comments_skipped += 1
                continue

            if para_idx >= len(docx_paragraphs):
                logger.warning(
                    f"Invalid paragraph index {para_idx} for chunk {comment.chunk_index}"
                )
                comments_skipped += 1
                continue

            try:
                paragraph = docx_paragraphs[para_idx]
                full_comment_text = comment.comment_text
                if comment.share_link:
                    full_comment_text += (
                        f"\n\n🔗 View in AI Reviewer: {comment.share_link}"
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
                text=comment_text,
                author=author,
                initials=initials,
            )
        except AttributeError as e:
            logger.warning(f"Error inserting comment to docx: {e}")
            raise


docx_manipulator_service = DocxManipulatorService()
