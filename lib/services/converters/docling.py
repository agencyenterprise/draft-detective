import logging
import mimetypes
import os

import aiofiles
import backoff
import httpx

from lib.config.env import config
from lib.services.converters.base import FileConverterProtocol

logger = logging.getLogger(__name__)


class DoclingConversionError(Exception):
    """Raised when docling conversion fails"""

    pass


class DoclingTimeoutError(DoclingConversionError):
    """Raised when docling conversion times out"""

    pass


class _TaskPending(Exception):
    """Internal exception to signal task needs more polling"""

    pass


class DoclingFileConverter(FileConverterProtocol):
    """Converts documents using docling-serve API with exponential backoff polling."""

    DEFAULT_TIMEOUT_MINUTES = 30
    TIMEOUT_PER_10MB_MINUTES = 15

    BACKOFF_FACTOR = 1.5
    BACKOFF_BASE = 2
    BACKOFF_MAX_WAIT = 10

    BASE_CONVERSION_PARAMS = {
        "from_formats": ["docx", "html", "pdf", "md"],
        "pipeline": "standard",
        "do_ocr": False,
        "force_ocr": False,
        "table_mode": "fast",
        "abort_on_error": False,
        "document_timeout": 600,
    }

    def __init__(self):
        self.base_url = config.DOCLING_SERVE_API_URL
        self.api_key = config.DOCLING_SERVE_API_KEY

    async def convert_to_markdown(self, file_path: str) -> str:
        """
        Convert file to markdown using docling-serve.

        Raises:
            DoclingConversionError: When conversion fails
            DoclingTimeoutError: When conversion times out
        """
        filename = os.path.basename(file_path)
        timeout_minutes = self._calculate_timeout(file_path)

        logger.info(f"Converting '{filename}' (timeout: {timeout_minutes}m)")

        async with self._create_client(timeout_minutes) as client:
            task_id = await self._submit_task(client, file_path)
            logger.info(f"Task {task_id} created for '{filename}'")

            await self._poll_until_complete(client, task_id, filename, timeout_minutes)

            response = await self._fetch_result(client, task_id)
            data = response.json()

        markdown = data.get("document", {}).get("md_content", "")
        logger.info(f"Successfully converted '{filename}'")
        return markdown

    def _calculate_timeout(self, file_path: str) -> int:
        """
        Calculate timeout based on file size.
        Formula: 15 minutes base + 2 minutes per 10MB
        Example: 50MB file = 15 + (5 * 2) = 25 minutes
        """
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            additional_minutes = int(file_size_mb / 10) * self.TIMEOUT_PER_10MB_MINUTES
            return self.DEFAULT_TIMEOUT_MINUTES + additional_minutes
        except OSError:
            return self.DEFAULT_TIMEOUT_MINUTES

    def _create_client(self, timeout_minutes: int) -> httpx.AsyncClient:
        """Create HTTP client with appropriate timeouts"""
        timeout = httpx.Timeout(
            connect=30.0,
            read=timeout_minutes * 60.0,
            write=120.0,
            pool=120.0,
        )
        return httpx.AsyncClient(timeout=timeout)

    def _build_conversion_params(self) -> dict:
        """Build docling API parameters for markdown conversion"""
        params = {**self.BASE_CONVERSION_PARAMS}
        params.update(
            {
                "to_formats": ["md"],
                "image_export_mode": "placeholder",
                "include_images": False,
            }
        )
        return params

    async def _submit_task(self, client: httpx.AsyncClient, file_path: str) -> str:
        """Submit conversion task to docling-serve, return task_id"""
        filename = os.path.basename(file_path)
        params = self._build_conversion_params()
        file_type = mimetypes.guess_type(filename)[0] or "text/plain"

        async with aiofiles.open(file_path, "rb") as f:
            file_content = await f.read()

        response = await client.post(
            f"{self.base_url}/v1/convert/file/async",
            files={"files": (filename, file_content, file_type)},
            data=params,
            headers={"X-Api-Key": self.api_key},
        )

        if response.status_code != 200:
            raise DoclingConversionError(
                f"Failed to submit '{filename}': {response.status_code} {response.text}"
            )

        return response.json()["task_id"]

    async def _check_task_status(
        self, client: httpx.AsyncClient, task_id: str, filename: str
    ) -> str:
        """Check task status and return status string"""
        response = await client.get(
            f"{self.base_url}/v1/status/poll/{task_id}",
            headers={"X-Api-Key": self.api_key},
        )
        task = response.json()
        status = task.get("task_status")

        logger.info(
            f"Task {task_id} [{filename}]: {status}, "
            f"position={task.get('task_position', '?')}"
        )

        if status == "failure":
            raise DoclingConversionError(f"Task failed for '{filename}'")

        return status

    async def _poll_until_complete(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        filename: str,
        timeout_minutes: int,
    ):
        """Poll task status with exponential backoff"""

        @backoff.on_exception(
            backoff.expo,
            (_TaskPending, httpx.ReadError, httpx.RemoteProtocolError),
            max_time=timeout_minutes * 60,
            factor=self.BACKOFF_FACTOR,
            base=self.BACKOFF_BASE,
            max_value=self.BACKOFF_MAX_WAIT,
            on_backoff=lambda d: logger.info(
                f"Task {task_id}: attempt {d['tries']}, waiting {d['wait']:.1f}s"
            ),
        )
        async def poll():
            status = await self._check_task_status(client, task_id, filename)
            if status != "success":
                raise _TaskPending()

        try:
            await poll()
        except _TaskPending:
            raise DoclingTimeoutError(
                f"Timeout after {timeout_minutes}m for '{filename}'"
            )

    async def _fetch_result(
        self, client: httpx.AsyncClient, task_id: str
    ) -> httpx.Response:
        """Fetch conversion result from docling-serve"""
        return await client.get(
            f"{self.base_url}/v1/result/{task_id}",
            headers={"X-Api-Key": self.api_key},
        )


docling_converter = DoclingFileConverter()
