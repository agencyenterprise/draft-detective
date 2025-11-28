import logging
import shutil
from pathlib import Path
from typing import List

from pydantic import BaseModel

from lib.config.env import config

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
    ) -> str:
        """
        Add comments to a DOCX file based on chunk indices.

        Args:
            original_docx_path: Path to the original .docx file
            comments: List of comments to add
            workflow_run_id: Workflow run ID for deterministic naming

        Returns:
            Path to the updated .docx file
        """
        original_path = Path(original_docx_path)

        if original_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"File must be .docx, got {original_path.suffix}")

        if not original_path.exists():
            raise FileNotFoundError(f"Original file not found: {original_docx_path}")

        output_path = self.get_output_path(workflow_run_id)

        # For now: Just copy the file (placeholder for future implementation)
        logger.info(
            f"Creating reviewed docx at {output_path} with {len(comments)} comments"
        )
        shutil.copy(original_docx_path, output_path)

        # TODO: Implement actual comment insertion using python-docx
        # This will involve:
        # 1. Chunk matching service to map chunk_index to docx paragraphs
        # 2. python-docx to add comments to matched paragraphs
        # 3. Handle edge cases (tables, images, etc.)

        logger.info(
            f"Successfully created reviewed docx with {len(comments)} placeholder comments"
        )
        return str(output_path)


docx_manipulator_service = DocxManipulatorService()

