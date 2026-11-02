"""Unit tests for `lib.services.converters.base` dispatch."""

from unittest.mock import AsyncMock, patch

import pytest

from lib.services.converters.base import convert_to_markdown


@pytest.mark.asyncio
async def test_markdown_files_are_read_verbatim(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Already markdown\n", encoding="utf-8")

    assert await convert_to_markdown(str(path)) == "# Already markdown\n"


@pytest.mark.asyncio
async def test_markitdown_dispatch_threads_keep_data_uris():
    with patch(
        "lib.services.converters.markitdown.markitdown_converter.convert_to_markdown",
        new=AsyncMock(return_value="converted"),
    ) as converter_mock:
        result = await convert_to_markdown(
            "/tmp/doc.docx", converter="markitdown", keep_data_uris=True
        )

    assert result == "converted"
    converter_mock.assert_awaited_once_with("/tmp/doc.docx", keep_data_uris=True)


@pytest.mark.asyncio
async def test_pypdfium_dispatch():
    with patch(
        "lib.services.converters.pypdfium.pypdfium_converter.convert_to_markdown",
        new=AsyncMock(return_value="pdf text"),
    ) as converter_mock:
        result = await convert_to_markdown("/tmp/doc.pdf", converter="pypdfium")

    assert result == "pdf text"
    converter_mock.assert_awaited_once_with("/tmp/doc.pdf")


@pytest.mark.asyncio
async def test_unknown_converter_is_rejected():
    with pytest.raises(ValueError, match="Invalid file converter"):
        await convert_to_markdown("/tmp/doc.docx", converter="pandoc")
