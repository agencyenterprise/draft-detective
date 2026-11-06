"""Replace browser-unrenderable drawings in a DOCX with rendered images.

Two kinds of drawing survive DOCX conversion badly: native charts
(``graphicData uri=".../chart"``), which carry no image bytes at all and are
dropped by mammoth silently, and EMF/WMF metafile pictures, which convert to
data URIs no browser can decode. Both need a real layout engine to rasterize,
and the only one available is LibreOffice.

Rendering goes through PDF, not LibreOffice's HTML export: the HTML filter
rasterizes at LibreOffice's default object size regardless of the size the
document declares — blurry, wrong aspect, frame lines clipped at the bitmap
edge. PDF export keeps drawings as vectors at their real size, so each
renderable drawing is isolated on its own page of a render-source copy,
exported to PDF once, and rendered at high resolution with pypdfium2. The
render source has zero page margins and zero paragraph spacing, which pins
each drawing to its page's top-left corner — so the crop is the drawing's
declared extent, computed geometrically, never guessed from visible pixels
(a borderless white chart has no visible outer bounds). The rendered image
is then spliced into the drawing in place of the original graphic,
preserving its declared extent.

A drawing is renderable only when it sits alone in a text-free top-level
paragraph — the shape Word produces for figures — so each PDF page contains
exactly one drawing and page order equals drawing order. Anything else is
left untouched.

The DOCX-export line mapper must see the same document structure as the
main-document conversion, or the markdown line numbers they derive would
disagree. It needs only the structure, not the pixels, so it uses
`stub_docx_drawings`: the same drawings swapped for a placeholder image, with
no LibreOffice render.
"""

import asyncio
import io
import logging
import os
import shutil
import tempfile
from typing import IO, Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from PIL import Image

# PDFium is not thread-safe; every pypdfium2 use in the codebase serializes on
# this lock (see lib/services/converters/pypdfium.py).
from lib.services.converters.pypdfium import _PDFIUM_LOCK

logger = logging.getLogger(__name__)

CHART_GRAPHIC_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
PICTURE_GRAPHIC_URI = "http://schemas.openxmlformats.org/drawingml/2006/picture"

_METAFILE_CONTENT_TYPES = {
    "image/emf",
    "image/x-emf",
    "image/wmf",
    "image/x-wmf",
}

_RENDER_TIMEOUT = 120
# 4× the PDF's 72 dpi user units ≈ 288 dpi — crisp at document display size.
_PDF_RENDER_SCALE = 4
_EMU_PER_POINT = 12700


async def rasterize_docx_drawings(docx_path: str) -> str | None:
    """Return a temp copy of ``docx_path`` with unrenderable drawings
    replaced by rendered images.

    Returns None when the document has nothing to render or rendering fails —
    the caller then converts the original document, whose charts drop and
    metafiles pass through unconverted (the behavior before this module
    existed). The caller owns deleting the returned file.
    """
    try:
        return await _rasterize_docx_drawings(docx_path)
    except Exception:
        # Rendering is an enhancement; a conversion must never fail over it.
        logger.warning("Drawing rasterization failed for %s", docx_path, exc_info=True)
        return None


async def _rasterize_docx_drawings(docx_path: str) -> str | None:
    document = Document(docx_path)
    renderable = [drawing for _, drawing in _renderable_paragraphs(document)]
    if not renderable:
        return None

    extents = [
        (int(extent.get("cx", "0")), int(extent.get("cy", "0")))
        for extent in (d.find(f".//{qn('wp:extent')}") for d in renderable)
    ]
    rendered = await _render_drawings_to_images(docx_path, extents)
    if rendered is None:
        return None
    tmp_render_dir, image_paths = rendered

    try:
        replaced = 0
        for drawing, image_path in zip(renderable, image_paths):
            if _replace_drawing_with_image(document, drawing, image_path):
                replaced += 1

        if replaced != len(renderable):
            # All or nothing: a partial replacement would make this run's
            # output structurally different from the next one's (splice
            # failures are transient), breaking line parity between
            # ingestion and export.
            logger.warning(
                "Drawing rasterization skipped for %s: replaced %d of %d drawings",
                docx_path,
                replaced,
                len(renderable),
            )
            return None

        out = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        out.close()
        document.save(out.name)
        logger.info("Rasterized %d drawing(s) in %s", replaced, docx_path)
        return out.name
    finally:
        shutil.rmtree(tmp_render_dir, ignore_errors=True)


def stub_docx_drawings(docx_path: str) -> str | None:
    """Return a temp copy of ``docx_path`` with every drawing
    `rasterize_docx_drawings` would render replaced by a 1×1 placeholder.

    The markdown converts to the same lines as the rasterized copy's (each
    picture is one image line, whatever its pixels), without the LibreOffice
    render, for callers that only need line numbers. Returns None when there
    is nothing to replace or a replacement fails, as `rasterize_docx_drawings`
    does. Synchronous; the caller owns deleting the returned file.
    """
    document = Document(docx_path)
    renderable = [drawing for _, drawing in _renderable_paragraphs(document)]
    if not renderable:
        return None
    placeholder = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(placeholder, format="PNG")
    for drawing in renderable:
        image = io.BytesIO(placeholder.getvalue())
        if not _replace_drawing_with_image(document, drawing, image):
            return None
    out = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    out.close()
    document.save(out.name)
    return out.name


def _is_render_target(document, drawing) -> bool:
    """A drawing browsers can't display: a chart, or a metafile picture."""
    graphic_data = drawing.find(f".//{qn('a:graphicData')}")
    if graphic_data is None:
        return False
    if graphic_data.get("uri") == CHART_GRAPHIC_URI:
        return True
    if graphic_data.get("uri") != PICTURE_GRAPHIC_URI:
        return False

    blip = graphic_data.find(f".//{qn('a:blip')}")
    embed_id = blip.get(qn("r:embed")) if blip is not None else None
    if not embed_id:
        return False
    try:
        part = document.part.related_parts[embed_id]
    except KeyError:
        return False
    return part.content_type in _METAFILE_CONTENT_TYPES


def _renderable_paragraphs(document) -> list[tuple[int, Any]]:
    """``(body child index, drawing)`` for every renderable drawing.

    A renderable drawing is a render target with a declared extent, sitting
    alone in a text-free top-level paragraph. Selection is by structural
    position, so two loads of the same file yield the same indices in the
    same order — that is what pairs each drawing with its page in the
    render-source PDF.
    """
    renderable: list[tuple[int, Any]] = []
    for index, element in enumerate(document.element.body):
        if element.tag != qn("w:p"):
            continue
        drawings = list(element.iter(qn("w:drawing")))
        # Only w:t nodes are visible run text; itertext() would also pick up
        # numeric internals like an anchored drawing's position offsets.
        text = "".join(t.text or "" for t in element.iter(qn("w:t")))
        if len(drawings) != 1 or text.strip():
            continue
        drawing = drawings[0]
        if drawing.find(f".//{qn('wp:extent')}") is None:
            continue  # no declared size to render or crop to
        if _is_render_target(document, drawing):
            renderable.append((index, drawing))
    return renderable


def _write_render_source_docx(src_path: str, dst_path: str) -> int:
    """Save a copy holding only the renderable drawings, one per page.

    Returns how many drawings the copy holds; its PDF page order equals
    ``_renderable_paragraphs`` order on the original document.
    """
    document = Document(src_path)
    kept_indices = {index for index, _ in _renderable_paragraphs(document)}

    body = document.element.body
    kept: list = []
    for index, element in enumerate(list(body)):
        if index in kept_indices:
            kept.append(element)
        elif element.tag != qn("w:sectPr"):  # keep page size and margins
            body.remove(element)

    for paragraph in kept[1:]:
        pPr = paragraph.get_or_add_pPr()
        if pPr.find(qn("w:pageBreakBefore")) is None:
            pPr.insert(0, OxmlElement("w:pageBreakBefore"))

    # Pin every drawing to its page's top-left corner so the crop can be
    # computed from the declared extent alone: anchored (floating) drawings
    # become inline so their position offsets can't move them out of the
    # crop, paragraphs are left-aligned (figures are typically centered) with
    # zero spacing and indentation, page margins are zero, and there are no
    # headers or footers.
    for paragraph in kept:
        for anchor in list(paragraph.iter(qn("wp:anchor"))):
            _convert_anchor_to_inline(anchor)
        pPr = paragraph.get_or_add_pPr()
        justification = pPr.find(qn("w:jc"))
        if justification is None:
            justification = OxmlElement("w:jc")
            pPr.append(justification)
        justification.set(qn("w:val"), "left")
        spacing = pPr.find(qn("w:spacing"))
        if spacing is None:
            spacing = OxmlElement("w:spacing")
            pPr.append(spacing)
        spacing.set(qn("w:before"), "0")
        spacing.set(qn("w:after"), "0")
        indent = pPr.find(qn("w:ind"))
        if indent is None:
            indent = OxmlElement("w:ind")
            pPr.append(indent)
        for attribute in ("w:left", "w:right", "w:firstLine", "w:hanging"):
            indent.set(qn(attribute), "0")

    for sectPr in document.element.iter(qn("w:sectPr")):
        margins = sectPr.find(qn("w:pgMar"))
        if margins is None:
            margins = OxmlElement("w:pgMar")
            sectPr.append(margins)
        for attribute in (
            "top",
            "right",
            "bottom",
            "left",
            "header",
            "footer",
            "gutter",
        ):
            margins.set(qn(f"w:{attribute}"), "0")

    for tag in ("w:headerReference", "w:footerReference"):
        for reference in list(document.element.iter(qn(tag))):
            reference.getparent().remove(reference)

    document.save(dst_path)
    return len(kept)


def _convert_anchor_to_inline(anchor) -> None:
    """Replace a floating drawing with an inline one of the same graphic.

    Anchors carry ``positionH``/``positionV`` offsets that would place the
    drawing away from the page origin the crop assumes; inline drawings flow
    with the (pinned) paragraph instead.
    """
    extent = anchor.find(qn("wp:extent"))
    graphic = anchor.find(qn("a:graphic"))
    if extent is None or graphic is None:
        return
    inline = parse_xml(
        f'<wp:inline {nsdecls("wp", "a")}><wp:docPr id="1" name="drawing"/></wp:inline>'
    )
    inline.insert(0, extent)  # moves the element
    inline.append(graphic)
    anchor.getparent().replace(anchor, inline)


def _render_pdf_pages(
    pdf_path: str, out_dir: str, extents: list[tuple[int, int]]
) -> list[str]:
    """Render every PDF page at high resolution, cropped to its drawing.

    The render source pins each drawing to its page's top-left corner, so the
    crop is simply the drawing's declared extent — a geometric fact, not a
    guess from visible pixels (a borderless white chart has no visible outer
    bounds to guess from), and the aspect ratio matches the display size by
    construction.
    """
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        paths: list[str] = []
        for index in range(min(len(pdf), len(extents))):
            page = pdf[index]
            try:
                image = page.render(scale=_PDF_RENDER_SCALE).to_pil()
            finally:
                page.close()
            cx, cy = extents[index]
            width = round(cx / _EMU_PER_POINT * _PDF_RENDER_SCALE)
            height = round(cy / _EMU_PER_POINT * _PDF_RENDER_SCALE)
            image = image.crop(
                (0, 0, min(width, image.width), min(height, image.height))
            )
            path = os.path.join(out_dir, f"drawing-{index}.png")
            image.save(path, format="PNG")
            paths.append(path)
        if len(pdf) != len(extents):
            return []  # page/drawing mismatch; caller bails on the count
        return paths
    finally:
        pdf.close()


async def _render_drawings_to_images(
    docx_path: str, extents: list[tuple[int, int]]
) -> tuple[str, list[str]] | None:
    """Render the document's renderable drawings; return (tmp_dir, image
    paths in drawing order), or None on failure. Caller removes tmp_dir."""
    expected = len(extents)
    libreoffice_cmd = shutil.which("soffice") or shutil.which("libreoffice")
    if not libreoffice_cmd:
        logger.warning("LibreOffice not found; drawings stay unrendered")
        return None

    # Ownership of tmp_dir transfers to the caller only on the successful
    # return; every other exit — early return, timeout, unexpected exception —
    # removes it here, or repeated failures would strand directories forever.
    tmp_dir = tempfile.mkdtemp(prefix="drawing-raster-")
    succeeded = False
    try:
        render_source = os.path.join(tmp_dir, "render-source.docx")
        if _write_render_source_docx(docx_path, render_source) != expected:
            logger.warning(
                "Drawing rasterization skipped for %s: render source does "
                "not match the drawing count",
                docx_path,
            )
            return None

        profile_dir = os.path.join(tmp_dir, "lo-profile")
        process = await asyncio.create_subprocess_exec(
            libreoffice_cmd,
            "--headless",
            # A private user profile per invocation: concurrent soffice
            # instances sharing the default profile silently fail.
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp_dir,
            render_source,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(), timeout=_RENDER_TIMEOUT
        )

        pdf_path = os.path.join(tmp_dir, "render-source.pdf")
        if process.returncode != 0 or not os.path.isfile(pdf_path):
            logger.warning(
                "LibreOffice PDF render failed: %s",
                stderr.decode() if stderr else "unknown error",
            )
            return None

        async with _PDFIUM_LOCK:
            image_paths = await asyncio.to_thread(
                _render_pdf_pages, pdf_path, tmp_dir, extents
            )

        if len(image_paths) != expected:
            logger.warning(
                "Drawing rasterization skipped for %s: %d rendered pages vs "
                "%d drawings",
                docx_path,
                len(image_paths),
                expected,
            )
            return None
        succeeded = True
        return tmp_dir, image_paths
    except TimeoutError:
        process.kill()
        await process.wait()
        logger.warning("LibreOffice PDF render timed out")
        return None
    finally:
        if not succeeded:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _replace_drawing_with_image(document, drawing, image: str | IO[bytes]) -> bool:
    """Swap a drawing's graphic for a picture of ``image`` (a path or stream)."""
    graphic_data = drawing.find(f".//{qn('a:graphicData')}")
    extent = drawing.find(f".//{qn('wp:extent')}")
    if graphic_data is None or extent is None:
        return False
    cx, cy = extent.get("cx", "0"), extent.get("cy", "0")

    try:
        rId, _ = document.part.get_or_add_image(image)
    except Exception:
        logger.warning("Could not add rendered drawing image", exc_info=True)
        return False

    pic_xml = (
        f"<pic:pic {nsdecls('pic', 'a', 'r')}>"
        f'<pic:nvPicPr><pic:cNvPr id="0" name="drawing"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rId}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        f"</pic:pic>"
    )
    for child in list(graphic_data):
        graphic_data.remove(child)
    graphic_data.set("uri", PICTURE_GRAPHIC_URI)
    graphic_data.append(parse_xml(pic_xml))
    return True
