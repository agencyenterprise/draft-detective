"""Unit tests for `lib.services.image_extraction`.

The invariant that matters most is line preservation: extraction rewrites each
image src in place, and issue anchors, `#L` links and the DOCX comment export
all assume the stored markdown's line numbers never move.
"""

import asyncio
import base64
import functools
import io
import os
import threading
import time
from unittest.mock import patch

import pytest
from PIL import Image, ImageCms
from xxhash import xxh128

from lib.services.docx.image_display_sizes import (
    DisplaySizes,
    ImagePlacement,
    SourceRect,
)
from lib.services import image_extraction
from lib.services.image_extraction import (
    EXTRACTED_IMAGES_DIRNAME,
    extract_data_uri_images,
    image_reference,
)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode()


def _uploads_patch(tmp_path):
    return patch(
        "lib.services.image_extraction.config.FILE_UPLOADS_MOUNT_PATH", str(tmp_path)
    )


@pytest.mark.asyncio
async def test_extracts_image_and_rewrites_src(tmp_path):
    markdown = f"Before.\n\n![Figure 1](data:image/png;base64,{PNG_B64})\n\nAfter."

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert len(result.images) == 1
    image = result.images[0]
    assert image.mime_type == "image/png"
    assert image.file_size == len(PNG_BYTES)
    assert image.line_number == 3
    assert image.alt == "Figure 1"
    assert os.path.isfile(image.image_path)
    assert image.image_path.startswith(
        os.path.join(str(tmp_path), EXTRACTED_IMAGES_DIRNAME)
    )
    with open(image.image_path, "rb") as f:
        assert f.read() == PNG_BYTES

    expected_src = image_reference(image.id)
    assert expected_src == f"draftdetective://{image.id}"
    assert result.markdown == f"Before.\n\n![Figure 1]({expected_src})\n\nAfter."


@pytest.mark.asyncio
async def test_line_count_is_preserved(tmp_path):
    markdown = (
        f"# Title\n\n![](data:image/png;base64,{PNG_B64})\n\n"
        f"Middle paragraph.\n\n![alt text](data:image/png;base64,{PNG_B64})\n"
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert result.markdown.count("\n") == markdown.count("\n")
    assert [img.line_number for img in result.images] == [3, 7]


@pytest.mark.asyncio
async def test_identical_images_share_one_disk_file_but_not_an_id(tmp_path):
    markdown = (
        f"![a](data:image/png;base64,{PNG_B64})\n"
        f"![b](data:image/png;base64,{PNG_B64})\n"
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert len(result.images) == 2
    assert result.images[0].image_path == result.images[1].image_path
    assert result.images[0].content_hash == result.images[1].content_hash
    # Each occurrence gets its own files row, so its own id and markdown src.
    assert result.images[0].id != result.images[1].id


@pytest.mark.asyncio
async def test_legacy_truncated_stub_is_left_untouched(tmp_path):
    """Documents converted before extraction existed carry `base64...` stubs."""
    markdown = "Text.\n\n![old figure](data:image/png;base64...)\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert result.images == []
    assert result.markdown == markdown


@pytest.mark.asyncio
async def test_undecodable_payload_is_skipped(tmp_path):
    """A corrupt base64 payload must not abort extraction of the others."""
    markdown = (
        "![bad](data:image/png;base64,AAAA=BADPADDING)\n"
        f"![good](data:image/png;base64,{PNG_B64})\n"
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert len(result.images) == 1
    assert result.images[0].line_number == 2
    assert "![bad](data:image/png;base64,AAAA=BADPADDING)" in result.markdown
    assert f"![good]({image_reference(result.images[0].id)})" in result.markdown


@pytest.mark.asyncio
async def test_markdown_without_images_is_returned_verbatim(tmp_path):
    markdown = "# Just text\n\nNo images anywhere.\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    assert result.markdown == markdown
    assert result.images == []
    assert not os.path.exists(os.path.join(str(tmp_path), EXTRACTED_IMAGES_DIRNAME))


@pytest.mark.asyncio
async def test_known_display_size_emits_sized_img_tag(tmp_path):
    sizes = DisplaySizes()
    content_hash = xxh128(PNG_BYTES).hexdigest()
    sizes.add(content_hash, ImagePlacement(width_px=150, height_px=48))
    sizes.add(content_hash, ImagePlacement(width_px=75, height_px=24))
    markdown = (
        f"![logo](data:image/png;base64,{PNG_B64})\n\n"
        f"![logo small](data:image/png;base64,{PNG_B64})\n"
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, sizes)

    first, second = result.images
    # Sizes are consumed in document order, so the same image content can
    # appear at two different sizes. The size rides in the reference's query
    # parameters so the image stays a plain (paragraph-wrapped) markdown image.
    assert f"![logo](draftdetective://{first.id}?w=150&h=48)" in result.markdown
    assert f"![logo small](draftdetective://{second.id}?w=75&h=24)" in result.markdown
    assert result.markdown.count("\n") == markdown.count("\n")


@pytest.mark.asyncio
async def test_unknown_display_size_keeps_markdown_image(tmp_path):
    markdown = f"![fig](data:image/png;base64,{PNG_B64})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, DisplaySizes())

    assert f"![fig](draftdetective://{result.images[0].id})" in result.markdown
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_write_leaves_no_temp_artifacts(tmp_path):
    """Images land via a temp name + atomic rename; the temp file must not
    survive, and the store must hold only content-addressed files."""
    markdown = f"![a](data:image/png;base64,{PNG_B64})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown)

    images_dir = os.path.join(str(tmp_path), EXTRACTED_IMAGES_DIRNAME)
    on_disk = sorted(os.listdir(images_dir))
    assert on_disk == [os.path.basename(result.images[0].image_path)]
    assert not any(name.endswith(".tmp") for name in on_disk)


@pytest.mark.asyncio
async def test_existing_image_file_is_not_rewritten(tmp_path):
    """Content-addressed files are immutable: a second extraction of the same
    bytes must not touch the existing file (readers may be serving it)."""
    from unittest.mock import patch as mock_patch

    markdown = f"![a](data:image/png;base64,{PNG_B64})\n"
    with _uploads_patch(tmp_path):
        first = await extract_data_uri_images(markdown)

        with mock_patch("lib.services.image_extraction.os.replace") as replace_mock:
            second = await extract_data_uri_images(markdown)

    replace_mock.assert_not_called()
    assert second.images[0].image_path == first.images[0].image_path


def _png_of(width: int, height: int) -> bytes:
    """A gradient PNG, so a crop is detectable from the stored pixels."""
    image = Image.new("RGB", (width, height))
    image.putdata(
        [
            (x * 255 // max(width - 1, 1), y * 255 // max(height - 1, 1), 0)
            for y in range(height)
            for x in range(width)
        ]
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _markdown_for(png: bytes) -> str:
    return f"![fig](data:image/png;base64,{base64.b64encode(png).decode()})\n"


def _sizes_for(png: bytes, placement: ImagePlacement) -> DisplaySizes:
    sizes = DisplaySizes()
    sizes.add(xxh128(png).hexdigest(), placement)
    return sizes


@pytest.mark.asyncio
async def test_declared_crop_is_applied_to_the_stored_image(tmp_path):
    """Word crops at display time and keeps the whole picture in the package,
    so the extent describes a region the raw bytes do not match. Storing the
    picture uncropped is what squashed Figure 1 of a real report."""
    png = _png_of(750, 450)
    # 17.222% off the top and 3.597% off the bottom leaves a 750x357 region,
    # which is what the drawing's 624x297 extent is shaped for.
    placement = ImagePlacement(
        width_px=624, height_px=297, crop=SourceRect(top=0.17222, bottom=0.03597)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    image = result.images[0]
    with Image.open(image.image_path) as stored:
        assert stored.size == (750, 357)
        assert abs(stored.width / stored.height - 624 / 297) < 0.01
    assert f"?w=624&h=297" in result.markdown


@pytest.mark.asyncio
async def test_cropped_image_is_addressed_by_its_cropped_bytes(tmp_path):
    """The stored file is content-addressed by what lands on disk, not by the
    bytes Word embedded — otherwise the same picture cropped two ways would
    collide on one file."""
    png = _png_of(400, 400)
    sizes = DisplaySizes()
    content_hash = xxh128(png).hexdigest()
    sizes.add(
        content_hash,
        ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5)),
    )
    sizes.add(
        content_hash,
        ImagePlacement(width_px=50, height_px=100, crop=SourceRect(right=0.5)),
    )
    markdown = _markdown_for(png) + _markdown_for(png)

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, sizes)

    top, left = result.images
    # Spelled out rather than chained: `a != b != c` would never compare a to c.
    assert top.content_hash != left.content_hash
    assert content_hash not in (top.content_hash, left.content_hash)
    assert top.image_path != left.image_path
    with Image.open(top.image_path) as stored:
        assert stored.size == (400, 200)
    with Image.open(left.image_path) as stored:
        assert stored.size == (200, 400)


@pytest.mark.asyncio
async def test_uncropped_image_is_stored_verbatim(tmp_path):
    """No crop means no re-encoding: identical bytes must keep deduplicating."""
    png = _png_of(300, 200)
    placement = ImagePlacement(width_px=150, height_px=100)

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert result.images[0].content_hash == xxh128(png).hexdigest()


@pytest.mark.asyncio
async def test_crop_too_small_to_change_a_pixel_leaves_bytes_untouched(tmp_path):
    """A sub-pixel crop must not force a re-encode, or content addressing
    would split one image into two files for no visible difference."""
    png = _png_of(100, 100)
    placement = ImagePlacement(
        width_px=100, height_px=100, crop=SourceRect(top=0.001, bottom=0.001)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=100&h=100" in result.markdown


@pytest.mark.asyncio
async def test_uncroppable_format_drops_the_declared_size(tmp_path):
    """The reference's `?w=&h=` describes the bytes on disk. When a crop
    cannot be applied, declaring the cropped region's size would stretch the
    uncropped image; the viewer's own proportions are the safer fallback."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'
    markdown = f"![fig](data:image/svg+xml;base64,{base64.b64encode(svg).decode()})\n"
    sizes = DisplaySizes()
    sizes.add(
        xxh128(svg).hexdigest(),
        ImagePlacement(width_px=200, height_px=50, crop=SourceRect(top=0.5)),
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, sizes)

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == svg
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_undecodable_image_bytes_drop_the_declared_size(tmp_path):
    """A PNG mime type on bytes Pillow cannot open: keep the image, drop the
    size that no longer describes it, and never fail the extraction."""
    junk = b"not really a png"
    markdown = f"![fig](data:image/png;base64,{base64.b64encode(junk).decode()})\n"
    sizes = DisplaySizes()
    sizes.add(
        xxh128(junk).hexdigest(),
        ImagePlacement(width_px=200, height_px=50, crop=SourceRect(left=0.25)),
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, sizes)

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == junk
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_outset_region_stores_the_picture_whole_and_drops_the_size(tmp_path):
    """A negative edge means Word pads that side, so the extent covers area
    the image does not contain. Clamping the outset away and cropping the
    opposite edge would store the wrong pixels under a size claiming to
    describe them; store the picture whole and declare nothing instead."""
    png = _png_of(400, 200)
    # A full-width band shifted left, not a 90%-wide crop.
    placement = ImagePlacement(
        width_px=400, height_px=200, crop=SourceRect(left=-0.1, right=0.1)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_overlapping_insets_drop_the_size(tmp_path):
    """Insets that leave no region are not a no-op. `crop_box` returns None
    for both, so without the `is_applicable` gate this would store the whole
    image and still declare the cropped size — the very distortion this
    change exists to prevent."""
    png = _png_of(300, 200)
    placement = ImagePlacement(
        width_px=100, height_px=200, crop=SourceRect(left=0.6, right=0.6)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_unreadable_crop_drops_the_size(tmp_path):
    """The document declared a crop we could not parse, so the region is
    unknown; the declared size cannot be trusted to describe the bytes."""
    png = _png_of(300, 200)
    placement = ImagePlacement(
        width_px=100, height_px=200, crop=SourceRect(unreadable=True)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_pure_outset_also_drops_the_size(tmp_path):
    """Padding on every side is still area the stored bytes do not cover."""
    png = _png_of(200, 200)
    placement = ImagePlacement(
        width_px=220, height_px=220, crop=SourceRect(left=-0.05, top=-0.05)
    )

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_oversized_image_is_not_decoded_for_a_crop(tmp_path):
    """`Image.open` reads the header only, but `crop` forces a full decode:
    Pillow's own bomb guard merely warns until twice its threshold, so a
    small, highly compressed raster could allocate hundreds of megabytes and
    take the worker down. Refuse the crop and drop the size instead."""
    png = _png_of(64, 64)
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))

    with (
        _uploads_patch(tmp_path),
        patch("lib.services.image_extraction._MAX_CROP_PIXELS", 64 * 64 - 1),
    ):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    with open(result.images[0].image_path, "rb") as f:
        assert f.read() == png
    assert "?w=" not in result.markdown


def test_the_real_pixel_cap_admits_a_600_dpi_page_scan():
    """The cap has to clear any figure a document can display; a 600 dpi
    letter-size scan (~34 MP) is the generous end of that range."""
    assert image_extraction._MAX_CROP_PIXELS >= 5100 * 6600
    assert image_extraction._MAX_CROP_PIXELS < Image.MAX_IMAGE_PIXELS


@pytest.mark.asyncio
async def test_cropping_runs_off_the_event_loop(tmp_path):
    """Decoding and re-encoding a print-resolution figure takes long enough to
    stall unrelated coroutines, and a document can hold several."""
    png = _png_of(400, 400)
    placement = ImagePlacement(width_px=400, height_px=200, crop=SourceRect(bottom=0.5))
    offloaded = []

    async def recording_to_thread(fn, *args, **kwargs):
        offloaded.append(fn)
        return fn(*args, **kwargs)

    with (
        _uploads_patch(tmp_path),
        patch.object(image_extraction.asyncio, "to_thread", recording_to_thread),
    ):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    assert image_extraction._crop_image in offloaded
    # ...and the offload did not cost correctness.
    with Image.open(result.images[0].image_path) as stored:
        assert stored.size == (400, 200)
    assert "?w=400&h=200" in result.markdown


def _oriented_jpeg(width: int, height: int, orientation: int) -> bytes:
    """A JPEG whose EXIF asks the viewer to rotate it 90 degrees."""
    image = Image.new("RGB", (width, height), "white")
    exif = image.getexif()
    exif[0x0112] = orientation
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_crop_follows_exif_orientation(tmp_path):
    """Word and browsers both display an EXIF-oriented photo rotated, so the
    declared crop describes the rotated view. Cropping the raw pixels would
    trim the wrong axis and, because the re-encode drops the orientation tag,
    also lay the photo on its side."""
    # 400x200 of pixels, displayed 200x400 because of the orientation tag.
    jpeg = _oriented_jpeg(400, 200, 6)
    # Half off the bottom of the *displayed* image: 200x400 -> 200x200.
    placement = ImagePlacement(width_px=200, height_px=200, crop=SourceRect(bottom=0.5))

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(
            f"![p](data:image/jpeg;base64,{base64.b64encode(jpeg).decode()})\n",
            _sizes_for(jpeg, placement),
        )

    with Image.open(result.images[0].image_path) as stored:
        # Upright and trimmed on the displayed axis, so no orientation tag is
        # needed to read it correctly any more.
        assert stored.size == (200, 200)
        assert stored.getexif().get(0x0112) is None
    assert "?w=200&h=200" in result.markdown


@pytest.mark.asyncio
async def test_unoriented_image_is_not_transposed(tmp_path):
    """`exif_transpose` copies the whole image, so it must not run for the
    overwhelmingly common case of a photo that needs no rotation."""
    png = _png_of(400, 200)
    placement = ImagePlacement(width_px=400, height_px=100, crop=SourceRect(bottom=0.5))

    with (
        _uploads_patch(tmp_path),
        patch.object(image_extraction.ImageOps, "exif_transpose") as transpose,
    ):
        result = await extract_data_uri_images(
            _markdown_for(png), _sizes_for(png, placement)
        )

    transpose.assert_not_called()
    with Image.open(result.images[0].image_path) as stored:
        assert stored.size == (400, 100)


@pytest.mark.asyncio
async def test_concurrent_crops_are_bounded_process_wide(tmp_path):
    """The pixel cap bounds one image; without this bound, crops from
    concurrently converting documents decode side by side and the totals
    still reach an OOM that no handler here gets to see."""
    png = _png_of(64, 64)
    placement = ImagePlacement(width_px=64, height_px=32, crop=SourceRect(bottom=0.5))
    in_flight, peak, guard = 0, 0, threading.Lock()
    real_crop_decoded = image_extraction._crop_decoded

    def observed(content, crop):
        nonlocal in_flight, peak
        with guard:
            in_flight += 1
            peak = max(peak, in_flight)
        try:
            time.sleep(0.02)
            return real_crop_decoded(content, crop)
        finally:
            with guard:
                in_flight -= 1

    with (
        _uploads_patch(tmp_path),
        patch.object(image_extraction, "_crop_decoded", observed),
    ):
        await asyncio.gather(
            *(
                extract_data_uri_images(_markdown_for(png), _sizes_for(png, placement))
                for _ in range(8)
            )
        )

    assert peak > 0, "the crop path did not run"
    assert peak <= 2


def _multi_frame(image_format: str, **save_options) -> bytes:
    first = Image.new("RGB", (100, 100), "red")
    second = Image.new("RGB", (100, 100), "blue")
    buffer = io.BytesIO()
    first.save(
        buffer,
        format=image_format,
        save_all=True,
        append_images=[second],
        **save_options,
    )
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("image_format", "mime_type", "save_options"),
    [
        ("WEBP", "image/webp", {"duration": 100}),
        ("TIFF", "image/tiff", {}),
        # APNG: a multi-frame PNG, which is easy to forget is one.
        ("PNG", "image/png", {"duration": 100}),
    ],
)
@pytest.mark.asyncio
async def test_multi_frame_images_are_never_cropped(
    tmp_path, image_format, mime_type, save_options
):
    """`crop(...).save(...)` writes one frame, so cropping an animated or
    multi-page picture would silently discard the rest of it. Keep the file
    whole and drop the size, as with an animated GIF."""
    content = _multi_frame(image_format, **save_options)
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))
    markdown = f"![a](data:{mime_type};base64,{base64.b64encode(content).decode()})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, _sizes_for(content, placement))

    with open(result.images[0].image_path, "rb") as f:
        stored = f.read()
    assert stored == content
    with Image.open(io.BytesIO(stored)) as image:
        assert image.n_frames == 2
    assert "?w=" not in result.markdown


@pytest.mark.asyncio
async def test_single_frame_image_of_a_multi_frame_format_still_crops(tmp_path):
    """The guard is per image, not per format: an ordinary one-frame WebP
    must not lose its crop because the container *can* animate."""
    image = Image.new("RGB", (100, 100), "red")
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP")
    content = buffer.getvalue()
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))
    markdown = f"![a](data:image/webp;base64,{base64.b64encode(content).decode()})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, _sizes_for(content, placement))

    with Image.open(result.images[0].image_path) as stored:
        assert stored.size == (100, 50)
    assert "?w=100&h=50" in result.markdown


@functools.cache
def _srgb_profile() -> bytes:
    # createProfile stamps the current time into the header, so two calls a
    # second apart differ by one byte. Build it once per test session.
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


@pytest.mark.parametrize(
    ("image_format", "mime_type"),
    [("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("PNG", "image/png")],
)
@pytest.mark.asyncio
async def test_cropped_image_keeps_its_icc_profile(tmp_path, image_format, mime_type):
    """The JPEG and WebP encoders read the profile from the save arguments,
    not from the decoded image, so an unpassed profile is a dropped one — and
    a Display P3 phone photo or a CMYK JPEG then renders with shifted colours."""
    image = Image.new("RGB", (100, 100), "red")
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, icc_profile=_srgb_profile())
    content = buffer.getvalue()
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))
    markdown = f"![a](data:{mime_type};base64,{base64.b64encode(content).decode()})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, _sizes_for(content, placement))

    with Image.open(result.images[0].image_path) as stored:
        assert stored.size == (100, 50)
        assert stored.info.get("icc_profile") == _srgb_profile()


@pytest.mark.asyncio
async def test_lossless_webp_stays_lossless_when_cropped(tmp_path):
    """A lossless WebP is usually a chart or a screenshot; re-encoding it lossy
    would put artefacts around its text."""
    image = Image.new("RGB", (100, 100), "red")
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", lossless=True)
    content = buffer.getvalue()
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))
    markdown = f"![a](data:image/webp;base64,{base64.b64encode(content).decode()})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, _sizes_for(content, placement))

    with open(result.images[0].image_path, "rb") as f:
        stored = f.read()
    assert b"VP8L" in stored
    with Image.open(io.BytesIO(stored)) as cropped:
        assert cropped.size == (100, 50)
        assert cropped.getpixel((0, 0)) == (255, 0, 0)  # lossless: exact colour


@pytest.mark.asyncio
async def test_jpeg_with_embedded_auxiliary_pictures_is_still_cropped(tmp_path):
    """Pillow opens a JPEG carrying an MPF segment (an embedded thumbnail or
    depth map, routine on phone cameras) as MPO with n_frames > 1. It displays
    as one picture everywhere, so the frame guard must not refuse it."""
    content = _multi_frame("MPO")
    placement = ImagePlacement(width_px=100, height_px=50, crop=SourceRect(bottom=0.5))
    markdown = f"![a](data:image/jpeg;base64,{base64.b64encode(content).decode()})\n"

    with _uploads_patch(tmp_path):
        result = await extract_data_uri_images(markdown, _sizes_for(content, placement))

    with Image.open(result.images[0].image_path) as stored:
        assert stored.format == "JPEG"
        assert stored.size == (100, 50)
    assert "?w=100&h=50" in result.markdown
