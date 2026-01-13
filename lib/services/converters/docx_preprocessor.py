import asyncio
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class DocxPreprocessor:
    """Converts DOCX files to PDF using LibreOffice headless mode"""

    SUPPORTED_EXTENSIONS = {".docx", ".doc"}
    CONVERSION_TIMEOUT = 60

    def _find_libreoffice(self) -> str:
        """Find LibreOffice executable path"""
        libreoffice_cmd = shutil.which("soffice") or shutil.which("libreoffice")
        if not libreoffice_cmd:
            raise RuntimeError(
                "LibreOffice not found. Install with: brew install --cask libreoffice"
            )
        return libreoffice_cmd

    async def _convert_with_libreoffice(
        self,
        file_path: str,
        output_format: str,
        output_suffix: str,
        format_name: str,
        should_convert: bool,
    ) -> str:
        """
        Internal method to perform LibreOffice conversion

        Args:
            file_path: Path to the input file
            output_format: LibreOffice format string (e.g., "docx", "pdf")
            output_suffix: Output file suffix (e.g., ".docx", ".pdf")
            format_name: Human-readable format name for logging (e.g., "DOCX", "PDF")
            should_convert: Whether the file should be converted

        Returns:
            Path to the converted file, or original path if conversion not needed

        Raises:
            RuntimeError: If LibreOffice is not found or conversion fails
        """
        file_path_obj = Path(file_path)

        if not should_convert:
            return file_path

        output_file = file_path_obj.with_suffix(output_suffix)

        if output_file.exists():
            return str(output_file)

        libreoffice_cmd = self._find_libreoffice()

        logger.info(f"Converting {file_path_obj.name} to {format_name}...")

        try:
            process = await asyncio.create_subprocess_exec(
                libreoffice_cmd,
                "--headless",
                "--convert-to",
                output_format,
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

            if not output_file.exists():
                raise RuntimeError(f"{format_name} not created")

            return str(output_file)

        except asyncio.TimeoutError as err:
            process.kill()
            await process.wait()
            raise RuntimeError(
                f"Conversion timed out after {self.CONVERSION_TIMEOUT}s"
            ) from err

    async def convert_doc_to_docx(self, file_path: str) -> str:
        """
        Convert DOC to DOCX using LibreOffice headless

        Args:
            file_path: Path to the .doc file

        Returns:
            Path to the converted .docx file, or original path if not a .doc file

        Raises:
            RuntimeError: If LibreOffice is not found or conversion fails
        """
        file_path_obj = Path(file_path)
        should_convert = file_path_obj.suffix.lower() == ".doc"

        return await self._convert_with_libreoffice(
            file_path=file_path,
            output_format="docx",
            output_suffix=".docx",
            format_name="DOCX",
            should_convert=should_convert,
        )

    async def convert_to_pdf(self, file_path: str) -> str:
        """
        Convert DOCX/DOC to PDF using LibreOffice headless

        Returns the PDF path, or original path if not a DOCX file
        """
        file_path_obj = Path(file_path)
        should_convert = file_path_obj.suffix.lower() in self.SUPPORTED_EXTENSIONS

        return await self._convert_with_libreoffice(
            file_path=file_path,
            output_format="pdf",
            output_suffix=".pdf",
            format_name="PDF",
            should_convert=should_convert,
        )


docx_preprocessor = DocxPreprocessor()
