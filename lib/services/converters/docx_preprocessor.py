import asyncio
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class DocxPreprocessor:
    """Converts DOCX files to PDF using LibreOffice headless mode"""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}
    CONVERSION_TIMEOUT = 30

    async def convert_to_pdf(self, file_path: str) -> str:
        """
        Convert DOCX/DOC to PDF using LibreOffice headless

        Returns the PDF path, or original path if not a DOCX file
        """
        file_path_obj = Path(file_path)

        if file_path_obj.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return file_path

        output_pdf = file_path_obj.with_suffix(".pdf")

        if output_pdf.exists():
            return str(output_pdf)

        libreoffice_cmd = shutil.which("soffice") or shutil.which("libreoffice")
        if not libreoffice_cmd:
            raise RuntimeError(
                "LibreOffice not found. Install with: brew install --cask libreoffice"
            )

        logger.info(f"Converting {file_path_obj.name} to PDF...")

        try:
            process = await asyncio.create_subprocess_exec(
                libreoffice_cmd,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(file_path_obj.parent),
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.CONVERSION_TIMEOUT,
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"LibreOffice failed: {error_msg}")

            if not output_pdf.exists():
                raise RuntimeError("PDF not created")

            return str(output_pdf)

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"Conversion timed out after {self.CONVERSION_TIMEOUT}s")


docx_preprocessor = DocxPreprocessor()
