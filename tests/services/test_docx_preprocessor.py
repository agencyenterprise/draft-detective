import pytest
import os
from pathlib import Path
from lib.services.converters.docx_preprocessor import docx_preprocessor


@pytest.mark.asyncio
async def test_should_preprocess_docx():
    """Test that DOCX files are identified for preprocessing"""
    assert await docx_preprocessor.should_preprocess("/path/to/file.docx")
    assert await docx_preprocessor.should_preprocess("/path/to/file.doc")
    assert await docx_preprocessor.should_preprocess("/path/to/FILE.DOCX")


@pytest.mark.asyncio
async def test_should_not_preprocess_other_formats():
    """Test that non-DOCX files are not preprocessed"""
    assert not await docx_preprocessor.should_preprocess("/path/to/file.pdf")
    assert not await docx_preprocessor.should_preprocess("/path/to/file.txt")
    assert not await docx_preprocessor.should_preprocess("/path/to/file.md")


@pytest.mark.asyncio
async def test_convert_to_pdf_passes_through_pdf():
    """Test that PDF files are returned as-is"""
    pdf_path = "/path/to/file.pdf"
    result = await docx_preprocessor.convert_to_pdf(pdf_path)
    assert result == pdf_path


@pytest.mark.asyncio
async def test_convert_to_pdf_skips_if_exists(tmp_path):
    """Test that conversion is skipped if PDF already exists"""
    # Create a dummy DOCX file
    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy content")

    # Create the expected PDF file
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("dummy pdf")

    result = await docx_preprocessor.convert_to_pdf(str(docx_file))
    assert result == str(pdf_file)


@pytest.mark.asyncio
async def test_convert_to_pdf_timeout_error(tmp_path, monkeypatch):
    """Test that timeout errors are properly handled"""
    import asyncio

    # Create a dummy DOCX file
    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy content")

    # Mock asyncio.wait_for to raise TimeoutError
    async def mock_wait_for(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    with pytest.raises(RuntimeError, match="timed out"):
        await docx_preprocessor.convert_to_pdf(str(docx_file))


@pytest.mark.asyncio
async def test_convert_to_pdf_libreoffice_not_found(tmp_path, monkeypatch):
    """Test that missing LibreOffice is properly handled"""
    import shutil

    # Create a dummy DOCX file
    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy content")

    # Mock shutil.which to return None (command not found)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    # Reset the cached command to force detection
    from lib.services.converters.docx_preprocessor import docx_preprocessor

    docx_preprocessor._libreoffice_cmd = None

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        await docx_preprocessor.convert_to_pdf(str(docx_file))

