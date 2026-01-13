import pytest
from lib.services.converters.docx_preprocessor import docx_preprocessor


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
    from unittest.mock import AsyncMock, MagicMock

    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy content")

    # Mock process that can be killed
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock()
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

    # Mock subprocess creation
    async def mock_create_subprocess(*args, **kwargs):
        return mock_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_create_subprocess)

    # Mock wait_for to raise TimeoutError
    async def mock_wait_for(coro, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    with pytest.raises(RuntimeError, match="timed out"):
        await docx_preprocessor.convert_to_pdf(str(docx_file))

    # Verify process was killed
    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called_once()


@pytest.mark.asyncio
async def test_convert_to_pdf_libreoffice_not_found(tmp_path, monkeypatch):
    """Test that missing LibreOffice is properly handled"""
    import shutil

    docx_file = tmp_path / "test.docx"
    docx_file.write_text("dummy content")

    # Mock shutil.which to return None (command not found)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        await docx_preprocessor.convert_to_pdf(str(docx_file))


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
async def test_convert_doc_to_docx_timeout_error(tmp_path, monkeypatch):
    """Test that timeout errors are properly handled for DOC to DOCX conversion"""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    doc_file = tmp_path / "test.doc"
    doc_file.write_text("dummy content")

    # Mock process that can be killed
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock()
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

    # Mock subprocess creation
    async def mock_create_subprocess(*args, **kwargs):
        return mock_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_create_subprocess)

    # Mock wait_for to raise TimeoutError
    async def mock_wait_for(coro, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    with pytest.raises(RuntimeError, match="timed out"):
        await docx_preprocessor.convert_doc_to_docx(str(doc_file))

    # Verify process was killed
    mock_process.kill.assert_called_once()
    mock_process.wait.assert_called_once()


@pytest.mark.asyncio
async def test_convert_doc_to_docx_libreoffice_not_found(tmp_path, monkeypatch):
    """Test that missing LibreOffice is properly handled for DOC to DOCX conversion"""
    import shutil

    doc_file = tmp_path / "test.doc"
    doc_file.write_text("dummy content")

    # Mock shutil.which to return None (command not found)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        await docx_preprocessor.convert_doc_to_docx(str(doc_file))
