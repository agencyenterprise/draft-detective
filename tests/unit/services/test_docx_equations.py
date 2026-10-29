"""Word equations survive DOCX conversion, one at a time."""

from pathlib import Path

import pytest
from docx import Document

from lib.services.converters.docx_equations import convert_docx_equations
from lib.services.converters.markitdown import markitdown_converter
from tests.conftest import write_docx_with_equations


@pytest.mark.asyncio
async def test_convertible_and_unconvertible_equations_both_survive(tmp_path: Path):
    docx_path = write_docx_with_equations(tmp_path / "equations.docx")

    markdown = await markitdown_converter.convert_to_markdown(docx_path)

    assert r"where $x\_{i}$ is the score for item i." in markdown
    assert "The entropy uses lnN for the base." in markdown


@pytest.mark.asyncio
async def test_display_equation_gets_its_own_line(tmp_path: Path):
    docx_path = write_docx_with_equations(tmp_path / "equations.docx")

    lines = (await markitdown_converter.convert_to_markdown(docx_path)).splitlines()

    assert r"$$x\_{i}$$" in lines
    assert "After the display equation." in lines


def test_document_without_equations_is_left_alone(tmp_path: Path):
    doc = Document()
    doc.add_paragraph("No maths here.")
    path = tmp_path / "plain.docx"
    doc.save(str(path))

    assert convert_docx_equations(str(path)) is None
