"""Unit tests for `lib.services.markdown_conversion`.

DB and converter dependencies are mocked; the file under test is just a thin
orchestrator over them, so the value is in pinning down its branching:
cached-markdown short-circuit, legacy `.doc` MIME / extension handling, and
the cache-write path in ``convert_and_cache_file_markdown``.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.file import FileDocument
from lib.services.markdown_conversion import (
    convert_and_cache_file_markdown,
    convert_file_document_to_markdown,
)

MODULE = "lib.services.markdown_conversion"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _file_document(
    *,
    file_path: str = "/uploads/abc.docx",
    file_type: str = DOCX_MIME,
    markdown: str = "",
) -> FileDocument:
    return FileDocument(
        file_id=str(uuid.uuid4()),
        file_path=file_path,
        file_name="main_document.docx",
        file_type=file_type,
        markdown=markdown,
        markdown_token_count=0,
    )


# --- convert_file_document_to_markdown ---


@pytest.mark.asyncio
async def test_returns_cached_markdown_unchanged():
    cached = _file_document(markdown="# already converted")

    with patch(f"{MODULE}.convert_to_markdown_fn") as convert_mock:
        result = await convert_file_document_to_markdown(cached)

    assert result is cached
    convert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_converts_modern_docx_via_markitdown():
    doc = _file_document(file_path="/uploads/abc.docx")

    with patch(
        f"{MODULE}.convert_to_markdown_fn",
        new=AsyncMock(return_value="# converted"),
    ) as convert_mock:
        result = await convert_file_document_to_markdown(doc)

    convert_mock.assert_awaited_once_with("/uploads/abc.docx", converter="markitdown")
    assert result is not doc
    assert result.markdown == "# converted"
    assert result.markdown_token_count > 0
    assert doc.markdown == ""  # original untouched (model_copy)


@pytest.mark.asyncio
async def test_legacy_doc_mime_is_preprocessed_to_docx():
    """`application/msword` triggers libreoffice conversion before markitdown."""
    doc = _file_document(file_path="/uploads/legacy.doc", file_type="application/msword")
    converted_path = "/uploads/legacy.docx"

    preprocessor = MagicMock()
    preprocessor.convert_doc_to_docx = AsyncMock(return_value=converted_path)

    with (
        patch(f"{MODULE}.docx_preprocessor", preprocessor),
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# legacy"),
        ) as convert_mock,
        patch(f"{MODULE}.os.remove") as remove_mock,
    ):
        result = await convert_file_document_to_markdown(doc)

    preprocessor.convert_doc_to_docx.assert_awaited_once_with("/uploads/legacy.doc")
    convert_mock.assert_awaited_once_with(converted_path, converter="markitdown")
    remove_mock.assert_called_once_with(converted_path)
    assert result.markdown == "# legacy"


@pytest.mark.asyncio
async def test_legacy_doc_extension_without_msword_mime_uses_copy_path():
    """`.doc` extension (with non-msword MIME) is handled by copying to `.docx`."""
    doc = _file_document(
        file_path="/uploads/legacy.doc",
        file_type="application/octet-stream",
    )

    with (
        patch(f"{MODULE}.shutil.copy") as copy_mock,
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# copied"),
        ) as convert_mock,
        patch(f"{MODULE}.os.remove") as remove_mock,
    ):
        result = await convert_file_document_to_markdown(doc)

    copy_mock.assert_called_once_with("/uploads/legacy.doc", "/uploads/legacy.docx")
    convert_mock.assert_awaited_once_with(
        "/uploads/legacy.docx", converter="markitdown"
    )
    remove_mock.assert_called_once_with("/uploads/legacy.docx")
    assert result.markdown == "# copied"


# --- convert_and_cache_file_markdown ---


def _file_row(*, has_cached: bool, file_id: str | None = None) -> SimpleNamespace:
    """Lightweight stand-in for a SQLModel `File` row."""
    return SimpleNamespace(
        id=file_id or str(uuid.uuid4()),
        has_cached_markdown=has_cached,
    )


@pytest.mark.asyncio
async def test_cache_skip_when_file_already_has_markdown():
    file_id = str(uuid.uuid4())
    file_row = _file_row(has_cached=True, file_id=file_id)

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=file_row)),
        patch(f"{MODULE}.load_file_document") as load_mock,
        patch(f"{MODULE}.update_file_artifacts") as update_mock,
    ):
        await convert_and_cache_file_markdown(file_id)

    load_mock.assert_not_called()
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_cache_persists_converted_markdown():
    file_id = str(uuid.uuid4())
    file_row = _file_row(has_cached=False, file_id=file_id)
    loaded = _file_document(markdown="")
    converted = loaded.model_copy(update={"markdown": "# fresh", "markdown_token_count": 2})

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=file_row)),
        patch(f"{MODULE}.load_file_document", new=AsyncMock(return_value=loaded)),
        patch(
            f"{MODULE}.convert_file_document_to_markdown",
            new=AsyncMock(return_value=converted),
        ),
        patch(f"{MODULE}.update_file_artifacts", new=AsyncMock()) as update_mock,
    ):
        await convert_and_cache_file_markdown(file_id)

    update_mock.assert_awaited_once_with(file_id=file_id, markdown="# fresh")


@pytest.mark.asyncio
async def test_cache_skips_write_when_conversion_yields_empty_markdown():
    """Empty markdown shouldn't overwrite the DB cache (logged + skipped)."""
    file_id = str(uuid.uuid4())
    file_row = _file_row(has_cached=False, file_id=file_id)
    loaded = _file_document(markdown="")
    empty_converted = loaded.model_copy(update={"markdown": "", "markdown_token_count": 0})

    with (
        patch(f"{MODULE}.get_file_by_id", new=AsyncMock(return_value=file_row)),
        patch(f"{MODULE}.load_file_document", new=AsyncMock(return_value=loaded)),
        patch(
            f"{MODULE}.convert_file_document_to_markdown",
            new=AsyncMock(return_value=empty_converted),
        ),
        patch(f"{MODULE}.update_file_artifacts", new=AsyncMock()) as update_mock,
    ):
        await convert_and_cache_file_markdown(file_id)

    update_mock.assert_not_called()
