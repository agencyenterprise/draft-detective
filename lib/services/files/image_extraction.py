"""Extract embedded data-URI images from converted markdown to disk.

markitdown (via mammoth) inlines DOCX images as base64 data URIs. Keeping those
in the stored markdown would bloat the ``files.markdown`` column and every LLM
prompt, so main-document conversion extracts the bytes to disk and rewrites
each src to a ``draftdetective://{file_id}`` reference, addressed by the
``files`` row the caller persists for it (role EXTRACTED_IMAGE). What lands on
disk is what the document *shows*: a picture Word crops (``a:srcRect``) is
stored cropped, because the size the reference declares describes the cropped
region and not the whole picture.

The scheme keeps persisted markdown independent of API routing: each consumer
resolves it to its own retrieval mechanism (the frontend to the download
endpoint, agents to an image tool). A rewrite never adds or removes lines:
each image stays on the single markdown line mammoth produced, which is what
keeps issue line anchors, ``#L`` links and the DOCX comment export valid.
"""

import asyncio
import base64
import binascii
import io
import logging
import os
import re
import threading
import uuid
from typing import Any

import aiofiles
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from xxhash import xxh128

from lib.config.env import config
from lib.services.docx.image_display_sizes import (
    DisplaySizes,
    ImagePlacement,
    SourceRect,
)

logger = logging.getLogger(__name__)

EXTRACTED_IMAGES_DIRNAME = "extracted_images"

# A full data-URI image as markitdown emits it with keep_data_uris=True.
# Legacy truncated stubs (`data:image/png;base64...`) have no comma and no
# base64 payload, so they never match and pass through untouched.
_DATA_URI_IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]\n]*)\]"
    r"\(data:(?P<mime>image/[\w.+-]+);base64,(?P<data>[A-Za-z0-9+/=]+)"
    r"(?P<title> \"[^\"\n]*\")?\)"
)

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "image/svg+xml": ".svg",
    # Metafiles are normally rendered to PNG upstream (drawing rasterization);
    # these land here only when that step was skipped. Browsers can't render
    # them, so the viewer shows the alt-text fallback.
    "image/emf": ".emf",
    "image/x-emf": ".emf",
    "image/wmf": ".wmf",
    "image/x-wmf": ".wmf",
}

# Formats a declared crop can be applied to. SVG and the metafiles are not
# raster. GIF is left out wholesale because an animated one would be flattened
# to a single frame; other formats carry multiple frames only occasionally, so
# they are admitted here and rejected per image by frame count in
# `_crop_decoded`.
_CROPPABLE_MIME_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/bmp", "image/tiff", "image/webp"}
)

# Cropping decodes the whole image, at roughly three bytes per pixel plus the
# cropped copy. 40 megapixels leaves room for a 600 dpi letter-size scan
# (~34 MP) — far beyond any figure a document displays — while keeping a
# decompression bomb from taking the worker down with it.
_MAX_CROP_PIXELS = 40_000_000

# How many images may be decoded for cropping at once, process-wide. Each
# in-flight crop holds the decoded image plus its cropped copy, so the cap
# above bounds one and this bounds their sum.
_CROP_SLOTS = threading.BoundedSemaphore(2)

# Encoders for which Pillow's `quality` means anything.
_LOSSY_SAVE_FORMATS = frozenset({"JPEG", "WEBP"})

# The chunk that holds a lossless WebP bitstream. Pillow does not report which
# encoding it decoded, and re-encoding a lossless source (a chart or a
# screenshot, typically) as lossy would put artefacts around its text.
_WEBP_LOSSLESS_CHUNK = b"VP8L"

# EXIF tag 0x0112, "Orientation": how the photo should be rotated for display.
_EXIF_ORIENTATION_TAG = 0x0112


class ExtractedImage(BaseModel):
    """Metadata for one image written to disk.

    ``id`` is generated here so the markdown can reference the image's future
    ``files`` row before it exists; the caller persists the row under this id.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    image_path: str
    mime_type: str
    file_size: int
    content_hash: str
    alt: str = ""


class ImageExtractionResult(BaseModel):
    markdown: str
    images: list[ExtractedImage]


# Storage-agnostic reference scheme used in persisted markdown. Never a URL:
# consumers translate it (the document viewers to the file-download endpoint,
# agents to their image tool), so API routes can move without touching rows.
IMAGE_REFERENCE_SCHEME = "draftdetective://"


def image_reference(
    image_file_id: uuid.UUID | str, display_size: tuple[int, int] | None = None
) -> str:
    """The src the rewritten markdown carries for an image's ``files`` row.

    The display size rides along as query parameters rather than as a raw
    ``<img>`` tag: a markdown image stays wrapped in a paragraph, which is
    what the viewers hang line numbers and issue anchoring on.
    """
    reference = f"{IMAGE_REFERENCE_SCHEME}{image_file_id}"
    if display_size and display_size[0] > 0 and display_size[1] > 0:
        reference += f"?w={display_size[0]}&h={display_size[1]}"
    return reference


async def extract_data_uri_images(
    markdown: str, display_sizes: DisplaySizes | None = None
) -> ImageExtractionResult:
    """Extract every full data-URI image in ``markdown`` to disk.

    Returns the markdown with each extracted image's src rewritten to
    ``image_reference`` plus the metadata needed to persist the images as
    ``files`` rows. Images whose placement is known (``display_sizes``, read
    from the source DOCX) are cropped to the region the document displays and
    carry its size in the reference's query parameters, so the viewer shows
    them the way the document does. Images that fail to decode are left
    untouched. Line count is preserved.
    """
    matches = list(_DATA_URI_IMAGE_RE.finditer(markdown))
    if not matches:
        return ImageExtractionResult(markdown=markdown, images=[])

    images_dir = os.path.join(config.FILE_UPLOADS_MOUNT_PATH, EXTRACTED_IMAGES_DIRNAME)
    os.makedirs(images_dir, exist_ok=True)

    images: list[ExtractedImage] = []
    pieces: list[str] = []
    cursor = 0
    for match in matches:
        try:
            content = base64.b64decode(match.group("data"), validate=True)
        except (binascii.Error, ValueError):
            logger.warning(
                "Skipping undecodable data-URI image at markdown line %d",
                markdown.count("\n", 0, match.start()) + 1,
            )
            continue

        mime_type = match.group("mime")
        # The placement is keyed by the hash of the bytes Word embedded, so it
        # is looked up before any crop is applied; the file on disk is then
        # addressed by the hash of what actually lands there.
        placement = (
            display_sizes.take(xxh128(content).hexdigest()) if display_sizes else None
        )
        content, placement = await _apply_declared_crop(content, mime_type, placement)
        image_path, content_hash = await _write_image(images_dir, content, mime_type)
        size = (placement.width_px, placement.height_px) if placement else None

        image = ExtractedImage(
            image_path=image_path,
            mime_type=mime_type,
            file_size=len(content),
            content_hash=content_hash,
            alt=match.group("alt"),
        )
        images.append(image)

        title = match.group("title") or ""
        replacement = f"![{image.alt}]({image_reference(image.id, size)}{title})"
        pieces.append(markdown[cursor : match.start()])
        pieces.append(replacement)
        cursor = match.end()

    pieces.append(markdown[cursor:])
    logger.info("Extracted %d embedded image(s) from markdown", len(images))
    return ImageExtractionResult(markdown="".join(pieces), images=images)


async def _apply_declared_crop(
    content: bytes, mime_type: str, placement: ImagePlacement | None
) -> tuple[bytes, ImagePlacement | None]:
    """Crop ``content`` to the region the document displays.

    Word keeps the whole picture in the package and crops at display time, so
    an uncropped extraction paired with the drawing's extent stretches the
    figure into a box shaped for a region it does not match. Cropping here
    also gives the agents' image tool the same view a reader gets.

    Returns the bytes to store and the placement to declare alongside them.
    The placement is dropped when a declared crop could not be applied: the
    reference's ``?w=&h=`` must always describe the region stored on disk, and
    without it the viewer falls back to the image's own proportions rather than
    distorting it.
    """
    crop = placement.crop if placement else None
    if crop is None:
        return content, placement
    if not crop.is_applicable:
        # The extent describes a region the stored bytes cannot be trimmed to
        # — padding, an unreadable edge, or overlapping insets. Keeping the
        # size would stretch the whole picture into it.
        logger.info("Not cropping image: %s is not a crop of it", crop)
        return content, None

    # Decoding and re-encoding a print-resolution figure takes long enough to
    # stall unrelated coroutines, and a document can hold several; the rest of
    # the conversion pipeline offloads its Pillow and LibreOffice work the same
    # way.
    cropped = await asyncio.to_thread(_crop_image, content, mime_type, crop)
    if cropped is None:
        return content, None
    return cropped, placement


def _crop_image(content: bytes, mime_type: str, crop: SourceRect) -> bytes | None:
    """``content`` cropped to ``crop``, or None when it cannot be applied.

    Admission control only; ``_crop_decoded`` does the work. Runs on a worker
    thread (see ``_apply_declared_crop``), so it must stay synchronous.
    """
    if mime_type not in _CROPPABLE_MIME_TYPES:
        logger.info("Not cropping %s image: format does not support it", mime_type)
        return None
    # The pixel cap below bounds one image; this bounds the process. Without
    # it, crops from concurrently converting documents decode side by side in
    # the shared executor and the totals still reach an OOM, which no
    # exception handler here gets to see. A threading primitive rather than an
    # asyncio one: it holds across every event loop and worker thread, and the
    # wait lands on a worker thread instead of the loop.
    with _CROP_SLOTS:
        try:
            return _crop_decoded(content, crop)
        except Exception:
            logger.warning("Could not apply declared image crop", exc_info=True)
            return None


def _crop_decoded(content: bytes, crop: SourceRect) -> bytes | None:
    """Decode, crop and re-encode ``content``; None when it must be left alone.

    A no-op crop returns the bytes untouched rather than re-encoding them, so
    content addressing keeps deduplicating images that are merely declared
    cropped.
    """
    with Image.open(io.BytesIO(content)) as image:
        image_format = image.format
        # `Image.open` reads the header only. Pillow's own bomb guard just
        # warns until twice its threshold, while `crop` forces a full decode,
        # so the pixel count is checked here first: a 450 KB 12000x12000 PNG
        # otherwise costs a third of a gigabyte.
        if image.width * image.height > _MAX_CROP_PIXELS:
            logger.warning(
                "Not cropping %dx%d image: above the %d pixel crop limit",
                image.width,
                image.height,
                _MAX_CROP_PIXELS,
            )
            return None
        if not image_format:
            return None
        # A JPEG carrying an MPF segment (an embedded thumbnail or depth map,
        # which phone cameras add routinely) opens as MPO with the auxiliary
        # pictures counted as frames. It displays as one picture everywhere,
        # so it is cropped as the JPEG it is; only the primary frame is kept.
        if image_format == "MPO":
            image_format = "JPEG"
        # `crop(...).save(...)` writes the current frame and nothing else, so
        # an animated or multi-page picture would come back with its other
        # frames silently gone. Same trade as the GIF exclusion above: a wrong
        # aspect ratio beats discarding what the file holds. Checked by frame
        # count rather than by format, which catches APNG and animated WebP
        # too, not just the containers usually thought of as multi-frame.
        frames = 1 if image_format == "JPEG" else getattr(image, "n_frames", 1)
        if frames > 1:
            logger.info(
                "Not cropping %s image: it has %d frames and cropping keeps one",
                image_format,
                frames,
            )
            return None

        # Word and browsers both display an EXIF-oriented photo rotated, so
        # the crop fractions describe the *rotated* view — applying them to
        # the raw pixels would crop the wrong axes. Normalise first and crop
        # in the orientation a reader sees; re-encoding then drops the
        # orientation tag, which by that point is correct. Only transpose
        # when the tag asks for it: the call copies the whole image.
        oriented: Image.Image = image
        if image.getexif().get(_EXIF_ORIENTATION_TAG, 1) != 1:
            oriented = ImageOps.exif_transpose(image)

        box = crop.crop_box(oriented.width, oriented.height)
        if box is None:
            return content
        buffer = io.BytesIO()
        options = _save_options(content, image_format, image.info.get("icc_profile"))
        oriented.crop(box).save(buffer, format=image_format, **options)
    return buffer.getvalue()


def _save_options(
    content: bytes, image_format: str, icc_profile: bytes | None
) -> dict[str, Any]:
    """Encoder settings that keep a cropped image looking like its source.

    Quality only reaches the encoders it means something to. JPEG re-encoding
    is lossy; 95 keeps the crop visually indistinguishable from the source at
    document display sizes. A lossless WebP stays lossless. The ICC profile is
    passed explicitly because the JPEG and WebP encoders read it from the save
    arguments, not from the decoded image: dropping it shifts the colours of
    every Display P3 phone photo and every CMYK JPEG.
    """
    options: dict[str, Any] = {}
    if image_format == "WEBP" and _WEBP_LOSSLESS_CHUNK in content:
        options["lossless"] = True
    elif image_format in _LOSSY_SAVE_FORMATS:
        options["quality"] = 95
    if icc_profile:
        options["icc_profile"] = icc_profile
    return options


async def _write_image(
    images_dir: str, content: bytes, mime_type: str
) -> tuple[str, str]:
    """Write image bytes content-addressed; reuse the file when it exists.

    Returns ``(image_path, content_hash)``.
    """
    content_hash = xxh128(content).hexdigest()
    extension = _MIME_EXTENSIONS.get(mime_type, ".bin")
    image_path = os.path.join(images_dir, content_hash + extension)

    if not os.path.exists(image_path):
        # Concurrent conversions can extract identical bytes; write to a
        # temporary name and move it into place atomically so a reader never
        # sees a partially-written file.
        temp_path = f"{image_path}.{uuid.uuid4().hex}.tmp"
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(content)
        os.replace(temp_path, image_path)
    return image_path, content_hash
