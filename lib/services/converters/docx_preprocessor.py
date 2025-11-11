import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DocxPreprocessor:
    """Converts DOCX files to PDF using LibreOffice headless mode"""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}
    CONVERSION_TIMEOUT = 30  # seconds

    def __init__(self):
        self._libreoffice_cmd: Optional[str] = None

    def _get_libreoffice_command(self) -> str:
        """
        Detect the LibreOffice command for this platform.
        - macOS: soffice
        - Linux/Docker: libreoffice
        """
        if self._libreoffice_cmd:
            return self._libreoffice_cmd

        # TODO: Seems soffice are available on both system.
        if shutil.which("soffice"):
            self._libreoffice_cmd = "soffice"
            logger.info("Using 'soffice' command (macOS)")
            return self._libreoffice_cmd

        if shutil.which("libreoffice"):
            self._libreoffice_cmd = "libreoffice"
            logger.info("Using 'libreoffice' command (Linux)")
            return self._libreoffice_cmd

        raise RuntimeError(
            "LibreOffice not found. Install it with: brew install --cask libreoffice (macOS) "
            "or apt-get install libreoffice-writer-nogui (Linux)"
        )

    async def should_preprocess(self, file_path: str) -> bool:
        """Check if file needs DOCX to PDF conversion"""
        extension = Path(file_path).suffix.lower()
        return extension in self.SUPPORTED_EXTENSIONS

    async def convert_to_pdf(self, file_path: str) -> str:
        """
        Convert DOCX/DOC to PDF using LibreOffice headless.

        Args:
            file_path: Path to the DOCX file

        Returns:
            Path to the converted PDF file

        Raises:
            RuntimeError: If conversion fails
        """
        if not await self.should_preprocess(file_path):
            return file_path

        file_path_obj = Path(file_path)
        output_dir = file_path_obj.parent
        output_pdf = file_path_obj.with_suffix(".pdf")

        if output_pdf.exists():
            logger.info(
                f"PDF already exists for {file_path_obj.name}, skipping conversion"
            )
            return str(output_pdf)

        logger.info(f"Converting {file_path_obj.name} to PDF using LibreOffice...")

        try:
            libreoffice_cmd = self._get_libreoffice_command()

            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    libreoffice_cmd,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(file_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.CONVERSION_TIMEOUT,
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(
                    f"LibreOffice conversion failed with code {result.returncode}: {error_msg}"
                )

            if not output_pdf.exists():
                raise RuntimeError(
                    f"Conversion appeared successful but PDF not found at {output_pdf}"
                )

            logger.info(
                f"Successfully converted {file_path_obj.name} to {output_pdf.name}"
            )
            return str(output_pdf)

        except asyncio.TimeoutError:
            logger.error(
                f"LibreOffice conversion timed out after {self.CONVERSION_TIMEOUT}s"
            )
            raise RuntimeError(
                f"Document conversion timed out after {self.CONVERSION_TIMEOUT} seconds"
            )
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during DOCX conversion: {str(e)}")
            raise RuntimeError(f"Document conversion failed: {str(e)}")


docx_preprocessor = DocxPreprocessor()
