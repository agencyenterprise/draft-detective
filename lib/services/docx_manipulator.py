import logging
from pathlib import Path
from typing import List

from docx import Document
from pydantic import BaseModel

from lib.agents.models import ValidatedDocument
from lib.config.env import config
from lib.services.docx_chunk_mapper import create_chunk_to_paragraph_mapping

logger = logging.getLogger(__name__)


class DocxComment(BaseModel):
    """Represents a comment to be added to a docx file"""

    chunk_index: int
    text: str
    author: str = "AI Reviewer"
    comment_text: str


class DocxManipulatorService:
    """Service for manipulating DOCX files with AI-generated comments"""

    SUPPORTED_EXTENSIONS = {".docx"}

    def get_output_path(self, workflow_run_id: str) -> Path:
        """Get the deterministic output path for a processed docx file"""
        output_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "processed_docx"
        output_dir.mkdir(exist_ok=True)
        return output_dir / f"{workflow_run_id}_reviewed.docx"

    async def add_comments_to_docx(
        self,
        original_docx_path: str,
        comments: List[DocxComment],
        workflow_run_id: str,
        chunks: List[ValidatedDocument] | None = None,
    ) -> str:
        """
        Add comments to a DOCX file based on chunk indices.

        Args:
            original_docx_path: Path to the original .docx file
            comments: List of comments to add
            workflow_run_id: Workflow run ID for deterministic naming
            chunks: Optional list of document chunks for mapping

        Returns:
            Path to the updated .docx file
        """
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
                    f"No paragraph mapping found for chunk {comment.chunk_index}, "
                    f"comment '{comment.comment_text}...' will be skipped"
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
                self._add_comment_to_paragraph(
                    doc, paragraph, comment.comment_text, comment.author
                )
                comments_added += 1
            except Exception as e:
                logger.error(
                    f"Failed to add comment to paragraph {para_idx}: {e}", exc_info=True
                )
                comments_skipped += 1

        doc.save(str(output_path))

        logger.info(
            f"Successfully created reviewed docx: {comments_added} comments added, "
            f"{comments_skipped} skipped"
        )
        return str(output_path)

    def _add_comment_to_paragraph(
        self, doc: Document, paragraph, comment_text: str, author: str
    ):
        """
        Add a comment to a paragraph.

        Args:
            doc: The Document object
            paragraph: The paragraph to add comment to
            comment_text: The comment text
            author: The comment author
        """
        try:
            doc.add_comment(
                runs=paragraph.runs if paragraph.runs else [paragraph.add_run("")],
                text=comment_text,
                author=author,
                initials=self._get_initials(author),
            )
        except AttributeError as e:
            logger.warning(f"Error inserting comment to docx: {e}")
            raise

    def _get_initials(self, author: str) -> str:
        """Get initials from author name"""
        parts = author.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        elif len(parts) == 1:
            return parts[0][:2].upper()
        return "AI"


docx_manipulator_service = DocxManipulatorService()
