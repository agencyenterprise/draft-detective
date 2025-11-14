"""
Service for processing ZIP files returned by docling-serve.

When using return_as_file=True, docling-serve returns a ZIP containing:
- *.json (the json_content)
- *.md (the markdown)
- artifacts/ (folder with images like image_000000_hash.png)
"""

import json
import logging
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DoclingZipProcessor:
    """Processes ZIP files returned by docling-serve"""

    def process_zip(self, zip_bytes: bytes, target_images_dir: Path) -> Dict[str, Any]:
        """
        Extract and process docling-serve ZIP file.

        Args:
            zip_bytes: The ZIP file contents as bytes
            target_images_dir: Directory where images should be saved

        Returns:
            dict with keys:
                - markdown: str (markdown content)
                - json_content: dict (parsed JSON content)
                - image_count: int (number of images extracted)
        """
        markdown = ""
        json_content = None
        image_count = 0

        try:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                file_list = zf.namelist()
                logger.info(f"ZIP contains {len(file_list)} files: {file_list}")

                md_file = self._find_file_by_extension(file_list, ".md")
                if md_file:
                    markdown = zf.read(md_file).decode("utf-8")
                    logger.info(
                        f"Extracted markdown from {md_file} ({len(markdown)} chars)"
                    )
                else:
                    logger.warning(f"No .md file found in ZIP")

                json_file = self._find_file_by_extension(file_list, ".json")
                if json_file:
                    json_content = json.loads(zf.read(json_file).decode("utf-8"))
                    logger.info(f"Extracted JSON from {json_file}")
                else:
                    logger.warning(f"No .json file found in ZIP")

                # Extract artifacts (images) - filter out directory entries
                all_artifacts = [f for f in file_list if f.startswith("artifacts/")]
                artifacts = [f for f in all_artifacts if not f.endswith("/")]

                if artifacts:
                    target_images_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(
                        f"Found {len(artifacts)} image files in artifacts/ folder, extracting to {target_images_dir}"
                    )

                    for artifact_path in artifacts:
                        # Extract just the filename (e.g., image_000000_hash.png)
                        filename = Path(artifact_path).name
                        target_path = target_images_dir / filename

                        # Write artifact to target directory
                        artifact_bytes = zf.read(artifact_path)
                        target_path.write_bytes(artifact_bytes)
                        image_count += 1

                    logger.info(
                        f"Extracted {image_count} images to {target_images_dir}"
                    )
                elif all_artifacts:
                    logger.warning(f"Found artifacts/ folder but no image files inside")
                else:
                    logger.info(
                        "No artifacts found in ZIP (document may not contain images)"
                    )

                # We need to process images in JSON because page images came as base64 data URIs.
                # 1. Extract base64 page images and save as files
                # 2. Update URIs in artifacts to point to renamed files
                if json_content:
                    base64_count = self._extract_base64_page_images(
                        json_content, target_images_dir
                    )
                    if base64_count > 0:
                        logger.info(
                            f"Extracted {base64_count} base64 page images to files"
                        )
                        image_count += base64_count

                    # Then update artifact URIs (rename image_XXX.png to page_N.png)
                    if image_count > 0:
                        self._update_image_uris(json_content, target_images_dir)

        except Exception as e:
            logger.error(f"Error processing docling ZIP: {e}", exc_info=True)
            raise

        return {
            "markdown": markdown,
            "json_content": json_content,
            "image_count": image_count,
        }

    def _find_file_by_extension(
        self, file_list: list[str], extension: str
    ) -> Optional[str]:
        """Find a file in the ZIP by extension, excluding directories"""
        for filename in file_list:
            if filename.endswith("/"):
                continue

            if filename.lower().endswith(extension.lower()):
                return filename
        return None

    def _iter_page_images(self, json_content: dict):
        """
        Yield (page_key, image_dict) for all valid page images.

        This helper reduces duplication when processing page images.
        """
        pages = json_content.get("pages", {})
        if not isinstance(pages, dict):
            return

        for page_key, page_data in pages.items():
            if not isinstance(page_data, dict):
                continue
            if "image" not in page_data:
                continue
            img = page_data["image"]
            if isinstance(img, dict) and "uri" in img:
                yield page_key, img

    def _extract_base64_page_images(self, json_content: dict, images_dir: Path) -> int:
        """
        Extract base64-encoded page images from JSON and save as files.

        Page images are stored in pages[N]['image']['uri'] as base64 data URIs.
        This extracts them, saves as page_N.png files, and updates the URIs.

        Returns:
            Number of base64 images extracted
        """
        import base64

        images_dir.mkdir(parents=True, exist_ok=True)
        extracted_count = 0

        for page_key, img in self._iter_page_images(json_content):
            image_uri = img["uri"]

            if not image_uri.startswith("data:"):
                continue

            try:
                if ";base64," in image_uri:
                    header, b64_data = image_uri.split(";base64,", 1)
                    image_format = header.split("/")[-1] if "/" in header else "png"
                else:
                    b64_data = (
                        image_uri.split(",", 1)[1] if "," in image_uri else image_uri
                    )
                    image_format = "png"

                image_bytes = base64.b64decode(b64_data)
                image_filename = f"page_{page_key}.{image_format}"
                image_path = images_dir / image_filename
                image_path.write_bytes(image_bytes)

                img["uri"] = image_filename
                extracted_count += 1
                logger.debug(f"Extracted base64 page image: {image_filename}")

            except Exception as e:
                logger.error(f"Failed to extract base64 image for page {page_key}: {e}")

        return extracted_count

    def _update_image_uris(self, json_content: dict, images_dir: Path) -> None:
        """
        Update image URIs in JSON content to reference extracted files.

        The JSON may contain image references pointing to artifacts/image_XXXXXX_hash.png.
        These are typically embedded figures/charts (not page screenshots).
        We keep the original artifact filenames and update URIs to point to them.
        """
        updated_count = 0

        for page_key, img in self._iter_page_images(json_content):
            original_uri = img["uri"]

            if "artifacts/" in original_uri:
                filename = Path(original_uri).name
                file_path = images_dir / filename

                if file_path.exists():
                    img["uri"] = filename
                    updated_count += 1
                    logger.debug(
                        f"Updated artifact URI for page {page_key}: {filename}"
                    )
                else:
                    logger.warning(f"Artifact file not found: {file_path}")

        if updated_count > 0:
            logger.info(f"Updated {updated_count} artifact image URIs")


docling_zip_processor = DoclingZipProcessor()
