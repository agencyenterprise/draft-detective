import base64
import logging
import mimetypes
import os
from asyncio import sleep
from pathlib import Path
from typing import Optional

import httpx

from lib.config.env import config
from lib.services.converters.base import FileConverterProtocol
from lib.services.docling_models import DoclingDocument

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5


class DoclingFileConverter(FileConverterProtocol):

    async def convert_to_markdown(self, file_path: str) -> str:
        """Convert file to markdown only (legacy method)"""
        full_result = await self.convert_with_docling(file_path)
        return full_result["markdown"]

    def _get_file_identifier(self, file_path: str) -> str:
        """
        Extract unique identifier from file path.
        Files are stored as {uploads_dir}/{xxhash}{extension}
        Returns just the xxhash part (filename without extension).
        """
        filename = os.path.basename(file_path)
        # Remove extension to get the xxhash
        file_id, _ = os.path.splitext(filename)
        return file_id

    def _get_images_directory(self, file_path: str) -> Path:
        """Get the directory where Docling images should be stored for this file"""
        file_id = self._get_file_identifier(file_path)
        images_dir = Path(config.FILE_UPLOADS_MOUNT_PATH) / "docling_images" / file_id
        return images_dir

    async def _download_referenced_images(
        self,
        json_content: dict,
        file_path: str,
        base_url: str,
        headers: dict,
        async_client: httpx.AsyncClient,
    ) -> None:
        """
        Download referenced images from Docling-serve and update URIs.

        Args:
            json_content: The Docling json_content dict (modified in place)
            file_path: Original file path (used to determine storage location)
            base_url: Docling-serve base URL
            headers: HTTP headers with API key
            async_client: Shared async HTTP client
        """
        pages = json_content.get("pages", {})
        if not isinstance(pages, dict):
            logger.warning("pages is not a dict, skipping image download")
            return

        # Create images directory
        images_dir = self._get_images_directory(file_path)
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created images directory: {images_dir}")

        downloaded_count = 0
        for page_key, page_data in pages.items():
            if not isinstance(page_data, dict):
                continue

            if "image" not in page_data:
                continue

            img = page_data["image"]
            if not isinstance(img, dict) or "uri" not in img:
                continue

            image_uri = img["uri"]

            # Skip if already base64 data
            if image_uri.startswith("data:"):
                logger.debug(f"Page {page_key}: image is already base64, skipping")
                continue

            try:
                # Construct full URL - the URI from Docling is relative
                # e.g., "/v1/result/{task_id}/images/page_0.png"
                if not image_uri.startswith("http"):
                    full_image_url = f"{base_url}{image_uri}"
                else:
                    full_image_url = image_uri

                logger.info(f"Downloading image from: {full_image_url}")

                # Download image
                response = await async_client.get(full_image_url, headers=headers)

                if response.status_code != 200:
                    logger.error(
                        f"Failed to download image for page {page_key}: "
                        f"HTTP {response.status_code}"
                    )
                    continue

                # Determine filename - extract from URI or use page_key
                if "/" in image_uri:
                    image_filename = os.path.basename(image_uri)
                else:
                    image_filename = f"page_{page_key}.png"

                # Save locally
                image_path = images_dir / image_filename
                image_path.write_bytes(response.content)
                logger.info(f"Saved image to: {image_path}")

                # Update URI to relative path that frontend can request
                # Frontend will request: /api/workflow-runs/{workflow_run_id}/pages/{image_filename}
                # Backend will look in: {uploads}/docling_images/{file_id}/{image_filename}
                img["uri"] = image_filename

                downloaded_count += 1

            except Exception as e:
                logger.error(
                    f"Error downloading image for page {page_key}: {e}", exc_info=True
                )
                continue

        logger.info(
            f"Downloaded {downloaded_count} images to {images_dir.relative_to(config.FILE_UPLOADS_MOUNT_PATH)}"
        )

    async def convert_with_docling(
        self, file_path: str
    ) -> dict[str, str | Optional[DoclingDocument]]:
        """
        Convert file using Docling and return both markdown and structured data

        Returns:
            dict with keys:
                - markdown: str (markdown content)
                - docling_document: DoclingDocument | None (raw json_content)
        """
        async_client = httpx.AsyncClient(timeout=60.0)
        base_url = config.DOCLING_SERVE_API_URL

        url = f"{base_url}/v1/convert/file/async"
        headers = {
            "X-Api-Key": config.DOCLING_SERVE_API_KEY,
        }
        parameters = {
            # See https://github.com/docling-project/docling-serve/blob/main/docs/usage.md for full list of parameters
            "from_formats": ["docx", "html", "pdf", "md"],
            "to_formats": ["md", "json"],  # Request both markdown and JSON
            # for reference files we want to run only the md
            "pipeline": "standard",
            "image_export_mode": "referenced",  # Use image references instead of embedded base64
            "include_images": True,  # Include page images as references
            "do_ocr": False,
            "force_ocr": False,
            "ocr_engine": "auto",
            "ocr_lang": ["en"],
            "table_mode": "fast",
            "abort_on_error": False,
            "document_timeout": 60 * 10,  # 10 minutes
        }
        filename = os.path.basename(file_path)
        file_type = mimetypes.guess_type(filename)[0] or "text/plain"

        with open(file_path, "rb") as file:
            files = {"files": (filename, file, file_type)}
            response = await async_client.post(
                url, files=files, data=parameters, headers=headers
            )

        if response.status_code != 200:
            raise Exception(
                f"Failed to convert file '{file_path}' using docling-serve: {response.status_code} {response.text}"
            )

        task = response.json()
        logger.info(
            f"Docling-serve task {task['task_id']} created for conversion of file '{filename}', polling for status"
        )

        while task["task_status"] not in ("success", "failure"):
            logger.info(
                f"Docling-serve task {task['task_id']} is {task['task_status']}, task position {task['task_position']}, polling again in {POLL_INTERVAL_SECONDS} seconds"
            )
            await sleep(POLL_INTERVAL_SECONDS)
            response = await async_client.get(
                f"{base_url}/v1/status/poll/{task['task_id']}", headers=headers
            )
            task = response.json()

        response = await async_client.get(
            f"{base_url}/v1/result/{task['task_id']}", headers=headers
        )
        data = response.json()

        if "document" in data:
            doc_keys = list(data["document"].keys())

        markdown = data["document"].get("md_content", "")

        docling_document = None
        json_content = data.get("document", {}).get("json_content")

        if json_content:
            # Download referenced images if using reference mode
            if parameters.get("image_export_mode") == "referenced":
                logger.info(
                    f"Downloading referenced images for '{filename}' from Docling-serve"
                )
                await self._download_referenced_images(
                    json_content, file_path, base_url, headers, async_client
                )

            # Pass through json_content as-is (spread into DoclingDocument)
            docling_document = DoclingDocument.from_json_content(json_content)
        else:
            logger.info(f"No json_content in response for '{filename}'")

        return {
            "markdown": markdown,
            "docling_document": docling_document,
        }


docling_converter = DoclingFileConverter()
