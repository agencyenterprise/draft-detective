"""DOCX manipulation service for adding AI-generated comments."""

import json
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional

from lxml import etree
from docx import Document
from docx.document import Document as DocumentObject
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

from lib.config.env import config
from lib.services.docx.chunk_mapper import ChunkLike, create_chunk_to_paragraph_mapping
from lib.workflows.models import SeverityEnum

logger = logging.getLogger(__name__)


# Severity mapping from workflow to DOCX
def _map_severity_enum_to_comment_severity(severity) -> "CommentSeverity":
    """Map workflow SeverityEnum to CommentSeverity."""
    mapping = {
        SeverityEnum.HIGH: CommentSeverity.HIGH,
        SeverityEnum.MEDIUM: CommentSeverity.MEDIUM,
        SeverityEnum.LOW: CommentSeverity.LOW,
        SeverityEnum.NONE: CommentSeverity.NONE,
    }
    return mapping.get(severity, CommentSeverity.NONE)


def _build_issue_anchor(issue) -> Optional[str]:
    """Build URL anchor fragment for an issue."""
    if issue.claim_index is not None and issue.chunk_index is not None:
        return f"#chunk-{issue.chunk_index}-claim-{issue.claim_index}"
    elif issue.chunk_index is not None:
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
    issue,
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


class DocxManipulatorService:
    """Service for manipulating DOCX files with AI-generated comments."""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}

    def get_output_path(self, workflow_run_id: str) -> Path:
        """Get the deterministic output path for a processed docx file."""
        output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
        output_dir.mkdir(exist_ok=True)
        return output_dir / f"{workflow_run_id}_reviewed.docx"

    async def add_addin_metadata_to_docx(
        self,
        original_docx_path: str,
        project_id: str,
        share_token: str,
        chunks: List[ChunkLike] | None = None,
    ) -> str:
        """Add custom properties and a comment to a DOCX file."""
        original_path = Path(original_docx_path)
        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
        output_dir.mkdir(exist_ok=True, parents=True)
        output_path = output_dir / f"{uuid.uuid4()}_with_metadata.docx"

        doc = Document(original_docx_path)
        docx_paragraphs = [p for p in doc.paragraphs if p.text.strip()]

        chunk_to_para_mapping = {}
        if chunks:
            chunk_to_para_mapping = create_chunk_to_paragraph_mapping(
                chunks, docx_paragraphs
            )

        doc.save(str(output_path))
        self.add_custom_property(output_path, "AIReviewer_ProjectId", project_id)
        self.add_custom_property(output_path, "AIReviewer_AuthToken", share_token)
        self.add_custom_property(
            output_path,
            "AIReviewer_ChunkToParagraphMapping",
            json.dumps(chunk_to_para_mapping) if chunk_to_para_mapping else None,
        )
        return str(output_path)

    async def add_comments_to_docx(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        chunks: List[ChunkLike] | None = None,
    ) -> str:
        """Add comments to a DOCX file based on chunk indices."""
        original_path = Path(original_docx_path)

        if original_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"File must be .docx, got {original_path.suffix}")

        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_path = self.get_output_path(workflow_run_id)
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

    def add_custom_property(self, docx_path, prop_name, prop_value, output_path=None):
        if output_path is None:
            output_path = docx_path

        CUSTOM_NS = (
            "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
        )
        VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
        CONTENT_TYPES_NS = (
            "http://schemas.openxmlformats.org/package/2006/content-types"
        )

        temp_dir = tempfile.mkdtemp()

        try:
            with zipfile.ZipFile(docx_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            docprops_dir = os.path.join(temp_dir, "docProps")
            os.makedirs(docprops_dir, exist_ok=True)

            custom_xml_path = os.path.join(docprops_dir, "custom.xml")

            # create custom.xml if it doesn't exist
            if os.path.exists(custom_xml_path):
                tree = etree.parse(custom_xml_path)
                root = tree.getroot()
            else:
                root = etree.Element(
                    f"{{{CUSTOM_NS}}}Properties", nsmap={None: CUSTOM_NS, "vt": VT_NS}
                )
                tree = etree.ElementTree(root)

            # find next available pid
            existing_pids = [
                int(p.get("pid"))
                for p in root.findall(f"{{{CUSTOM_NS}}}property")
                if p.get("pid") is not None
            ]
            next_pid = max(existing_pids, default=1) + 1

            # check if property already exists
            for prop in root.findall(f"{{{CUSTOM_NS}}}property"):
                if prop.get("name") == prop_name:
                    root.remove(prop)

            # create new property
            prop_el = etree.SubElement(
                root,
                f"{{{CUSTOM_NS}}}property",
                {
                    "fmtid": "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}",
                    "pid": str(next_pid),
                    "name": prop_name,
                },
            )

            val_el = etree.SubElement(prop_el, f"{{{VT_NS}}}lpwstr")
            val_el.text = str(prop_value) if prop_value is not None else ""

            # write custom.xml
            tree.write(
                custom_xml_path,
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=True,
            )

            # update [Content_Types].xml
            content_types_path = os.path.join(temp_dir, "[Content_Types].xml")
            ct_tree = etree.parse(content_types_path)
            ct_root = ct_tree.getroot()

            override_xpath = f"{{{CONTENT_TYPES_NS}}}Override"
            exists = False

            for child in ct_root.findall(override_xpath):
                if child.get("PartName") == "/docProps/custom.xml":
                    exists = True
                    break

            if not exists:
                etree.SubElement(
                    ct_root,
                    override_xpath,
                    {
                        "PartName": "/docProps/custom.xml",
                        "ContentType": "application/vnd.openxmlformats-officedocument.custom-properties+xml",
                    },
                )

            ct_tree.write(
                content_types_path,
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=True,
            )

            # zip back
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
                for foldername, _, filenames in os.walk(temp_dir):
                    for filename in filenames:
                        filepath = os.path.join(foldername, filename)
                        arcname = os.path.relpath(filepath, temp_dir)
                        zip_out.write(filepath, arcname)

        finally:
            shutil.rmtree(temp_dir)


docx_manipulator_service = DocxManipulatorService()
