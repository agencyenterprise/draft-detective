"""Integration tests for drawing rasterization — require LibreOffice.

Covers the two things the unit tests cannot: the real render leg
(LibreOffice PDF export + pypdfium2), and the line-parity contract — the
paragraph line mapper and the main conversion must agree on line numbers for
documents whose rasterized drawings insert markdown lines.
"""

import base64
import io
import os
import re
import shutil
import struct
from unittest.mock import patch

import pytest
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from PIL import Image

from lib.services.converters.base import convert_to_markdown
from lib.services.docx.drawing_rasterization import (
    CHART_GRAPHIC_URI,
    PICTURE_GRAPHIC_URI,
    rasterize_docx_drawings,
)
from lib.services.docx.paragraph_line_mapper import build_paragraph_line_ranges

pytestmark = pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice not installed",
)


def _minimal_emf() -> bytes:
    """A syntactically valid, visually blank EMF (header + EOF records)."""
    header = struct.pack(
        "<II4i4iIIIIHHIIIiiii",
        1,  # EMR_HEADER
        88,  # record size
        0,
        0,
        99,
        99,  # rclBounds (device units)
        0,
        0,
        2646,
        2646,  # rclFrame (0.01 mm)
        0x464D4520,  # " EMF" signature
        0x00010000,  # version
        108,  # total bytes
        2,  # records
        1,  # handles
        0,  # reserved
        0,  # description length
        0,  # description offset
        0,  # palette entries
        1024,
        768,  # device size in pixels
        320,
        240,  # device size in millimeters
    )
    eof = struct.pack("<IIIII", 14, 20, 0, 16, 20)  # EMR_EOF
    return header + eof


def _append_paragraph_xml(document, inner: str) -> None:
    xml = f"<w:p {nsdecls('w', 'wp', 'a', 'r', 'c', 'pic')}><w:r>{inner}</w:r></w:p>"
    document.element.body.get_or_add_sectPr().addprevious(parse_xml(xml))


def _chart_drawing_xml() -> str:
    return (
        "<w:drawing><wp:inline>"
        '<wp:extent cx="1828800" cy="914400"/>'
        f'<a:graphic><a:graphicData uri="{CHART_GRAPHIC_URI}">'
        '<c:chart r:id="rId999"/>'
        "</a:graphicData></a:graphic>"
        "</wp:inline></w:drawing>"
    )


def _emf_drawing_xml(embed_id: str) -> str:
    return (
        "<w:drawing><wp:inline>"
        '<wp:extent cx="1828800" cy="914400"/>'
        f'<a:graphic><a:graphicData uri="{PICTURE_GRAPHIC_URI}">'
        "<pic:pic>"
        '<pic:nvPicPr><pic:cNvPr id="0" name="emf"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{embed_id}"/></pic:blipFill>'
        "<pic:spPr/>"
        "</pic:pic>"
        "</a:graphicData></a:graphic>"
        "</wp:inline></w:drawing>"
    )


def _build_document_with_chart(tmp_path) -> tuple[str, list[str]]:
    """A document of unique text paragraphs with a chart in the middle."""
    document = Document()
    texts = [f"PARAGRAPH-{i} distinctive body text." for i in range(6)]
    for i, text in enumerate(texts):
        document.add_paragraph(text)
        if i == 2:
            _append_paragraph_xml(document, _chart_drawing_xml())
    path = str(tmp_path / "chart-doc.docx")
    document.save(path)
    return path, texts


async def _stored_markdown(docx_path: str) -> str:
    """The markdown the app persists: rasterize, then convert."""
    rasterized = await rasterize_docx_drawings(docx_path)
    try:
        return await convert_to_markdown(
            rasterized or docx_path, converter="markitdown", keep_data_uris=True
        )
    finally:
        if rasterized:
            os.remove(rasterized)


@pytest.mark.asyncio
async def test_chart_document_line_parity_with_paragraph_mapper(tmp_path):
    """The mapper's line ranges must point at the right lines of the stored
    markdown even though the rendered chart inserted lines into it."""
    docx_path, texts = _build_document_with_chart(tmp_path)

    markdown = await _stored_markdown(docx_path)
    # The chart really rendered — otherwise parity would hold trivially.
    assert "data:image" in markdown

    ranges = await build_paragraph_line_ranges(
        docx_path, expected_line_count=markdown.count("\n") + 1
    )
    lines = markdown.split("\n")

    assert len(ranges) == len(texts)
    for index, text in enumerate(texts):
        start, end = ranges[index]
        window = "\n".join(lines[start - 1 : end])
        assert text in window, f"paragraph {index} range {start}-{end} misses its text"


@pytest.mark.asyncio
async def test_chart_is_rendered_between_its_neighbors(tmp_path):
    docx_path, texts = _build_document_with_chart(tmp_path)

    markdown = await _stored_markdown(docx_path)
    lines = markdown.split("\n")

    image_lines = [i for i, line in enumerate(lines) if "data:image" in line]
    assert len(image_lines) == 1
    before = next(i for i, line in enumerate(lines) if texts[2] in line)
    after = next(i for i, line in enumerate(lines) if texts[3] in line)
    assert before < image_lines[0] < after


@pytest.mark.asyncio
async def test_metafile_picture_is_rendered_to_png(tmp_path):
    document = Document()
    document.add_paragraph("Before the metafile.")
    part = Part(
        PackURI("/word/media/image1.emf"),
        "image/x-emf",
        _minimal_emf(),
        document.part.package,
    )
    embed_id = document.part.relate_to(part, RT.IMAGE)
    _append_paragraph_xml(document, _emf_drawing_xml(embed_id))
    document.add_paragraph("After the metafile.")
    docx_path = str(tmp_path / "emf-doc.docx")
    document.save(docx_path)

    markdown = await _stored_markdown(docx_path)

    assert "data:image/png" in markdown
    assert "x-emf" not in markdown


@pytest.mark.asyncio
async def test_mapper_refuses_to_anchor_when_rasterization_diverges(tmp_path):
    """Ingestion rendered the chart (stored markdown has its lines) but the
    export cannot stand a placeholder in for it: anchoring against a
    structurally different conversion would misplace every later comment, so
    the mapper must return nothing instead."""
    docx_path, _ = _build_document_with_chart(tmp_path)
    markdown = await _stored_markdown(docx_path)
    assert "data:image" in markdown

    with patch(
        "lib.services.docx.paragraph_line_mapper.stub_docx_drawings",
        return_value=None,
    ):
        ranges = await build_paragraph_line_ranges(
            docx_path, expected_line_count=markdown.count("\n") + 1
        )

    assert ranges == {}


@pytest.mark.asyncio
async def test_rendered_chart_keeps_declared_aspect_ratio(tmp_path):
    """Geometric cropping must hold even for a blank/borderless drawing,
    where visible-pixel cropping has nothing to anchor on."""
    docx_path, _ = _build_document_with_chart(tmp_path)
    markdown = await _stored_markdown(docx_path)

    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", markdown)
    assert match
    image = Image.open(io.BytesIO(base64.b64decode(match.group(1))))
    # The synthetic chart has no chart part behind it, so it renders blank —
    # exactly the case where only a geometric crop preserves the 2:1 extent.
    assert abs(image.width / image.height - 2.0) < 0.01


@pytest.mark.asyncio
async def test_anchored_chart_is_rendered_at_declared_extent(tmp_path):
    """Floating drawings carry position offsets; the render source converts
    them to inline so the geometric crop still holds."""
    anchored_chart = (
        "<w:drawing><wp:anchor>"
        '<wp:positionH relativeFrom="page"><wp:posOffset>1500000</wp:posOffset></wp:positionH>'
        '<wp:positionV relativeFrom="page"><wp:posOffset>2500000</wp:posOffset></wp:positionV>'
        '<wp:extent cx="1828800" cy="914400"/>'
        f'<a:graphic><a:graphicData uri="{CHART_GRAPHIC_URI}">'
        '<c:chart r:id="rId999"/>'
        "</a:graphicData></a:graphic>"
        "</wp:anchor></w:drawing>"
    )
    document = Document()
    document.add_paragraph("Before the floating chart.")
    _append_paragraph_xml(document, anchored_chart)
    document.add_paragraph("After the floating chart.")
    docx_path = str(tmp_path / "anchored-chart.docx")
    document.save(docx_path)

    markdown = await _stored_markdown(docx_path)

    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", markdown)
    assert match
    image = Image.open(io.BytesIO(base64.b64decode(match.group(1))))
    assert abs(image.width / image.height - 2.0) < 0.01
