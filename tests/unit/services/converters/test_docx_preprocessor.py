import shutil

import pytest

from lib.services.converters.docx_preprocessor import docx_preprocessor


@pytest.mark.asyncio
async def test_convert_doc_to_docx_passes_through_docx():
    """Test that DOCX files are returned as-is"""
    docx_path = "/path/to/file.docx"
    result = await docx_preprocessor.convert_doc_to_docx(docx_path)
    assert result == docx_path


@pytest.mark.asyncio
async def test_convert_doc_to_docx_skips_if_exists(tmp_path):
    """Test that conversion is skipped if DOCX already exists"""
    # Create a dummy DOC file
    doc_file = tmp_path / "test.doc"
    doc_file.write_text("dummy content")

    # Create the expected DOCX file
    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy docx")

    result = await docx_preprocessor.convert_doc_to_docx(str(doc_file))
    assert result == str(docx_file)


@pytest.mark.asyncio
async def test_convert_doc_to_docx_libreoffice_not_found(tmp_path, monkeypatch):
    """Test that missing LibreOffice is properly handled for DOC to DOCX conversion"""
    doc_file = tmp_path / "test.doc"
    doc_file.write_text("dummy content")

    # Mock shutil.which to return None (command not found)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        await docx_preprocessor.convert_doc_to_docx(str(doc_file))
