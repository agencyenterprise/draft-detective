"""Unit tests for `lib.services.markdown_conversion`.

DB and converter dependencies are mocked; the file under test is just a thin
orchestrator over them, so the value is in pinning down its branching:
cached-markdown short-circuit, legacy `.doc` MIME / extension handling, and
the cache-write path in ``convert_and_cache_file_markdown``.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.models.file import FileRole
from lib.services.file import FileDocument
from lib.services.markdown_conversion import (
    _converter_for,
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

    with (
        patch(f"{MODULE}.rasterize_docx_drawings", new=AsyncMock(return_value=None)),
        patch(
            f"{MODULE}.replace_extracted_images", new=AsyncMock()
        ) as replace_images_mock,
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# converted"),
        ) as convert_mock,
    ):
        result = await convert_file_document_to_markdown(doc)

    convert_mock.assert_awaited_once_with(
        "/uploads/abc.docx", converter="markitdown", keep_data_uris=True
    )
    assert result is not doc
    assert result.markdown == "# converted"
    assert result.markdown_token_count > 0
    assert doc.markdown == ""  # original untouched (model_copy)
    # Rows are replaced even when extraction finds nothing, so reconversion
    # clears children a previous conversion created.
    replace_images_mock.assert_awaited_once_with(doc.file_id, [])


@pytest.mark.asyncio
async def test_legacy_doc_mime_is_preprocessed_to_docx():
    """`application/msword` triggers libreoffice conversion before markitdown."""
    doc = _file_document(file_path="/uploads/legacy.doc", file_type="application/msword")
    converted_path = "/uploads/legacy.docx"

    preprocessor = MagicMock()
    preprocessor.convert_doc_to_docx = AsyncMock(return_value=converted_path)

    with (
        patch(f"{MODULE}.docx_preprocessor", preprocessor),
        patch(f"{MODULE}.rasterize_docx_drawings", new=AsyncMock(return_value=None)),
        patch(
            f"{MODULE}.replace_extracted_images", new=AsyncMock()
        ) as replace_images_mock,
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# legacy"),
        ) as convert_mock,
        patch(f"{MODULE}.os.remove") as remove_mock,
    ):
        result = await convert_file_document_to_markdown(doc)

    preprocessor.convert_doc_to_docx.assert_awaited_once_with("/uploads/legacy.doc")
    convert_mock.assert_awaited_once_with(
        converted_path, converter="markitdown", keep_data_uris=True
    )
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
        patch(f"{MODULE}.rasterize_docx_drawings", new=AsyncMock(return_value=None)),
        patch(
            f"{MODULE}.replace_extracted_images", new=AsyncMock()
        ) as replace_images_mock,
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# copied"),
        ) as convert_mock,
        patch(f"{MODULE}.os.remove") as remove_mock,
    ):
        result = await convert_file_document_to_markdown(doc)

    copy_mock.assert_called_once_with("/uploads/legacy.doc", "/uploads/legacy.docx")
    convert_mock.assert_awaited_once_with(
        "/uploads/legacy.docx", converter="markitdown", keep_data_uris=True
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

# --- _converter_for ---


@pytest.mark.parametrize(
    ("path", "role", "expected"),
    [
        ("/uploads/a.pdf", FileRole.MAIN, "markitdown"),
        ("/uploads/a.pdf", FileRole.REVIEWER_MEMO, "markitdown"),
        ("/uploads/a.pdf", FileRole.RESPONSE_MEMO, "markitdown"),
        ("/uploads/a.pdf", FileRole.SUPPORT, "pypdfium"),
        ("/uploads/a.docx", FileRole.SUPPORT, "markitdown"),
    ],
)
def test_converter_for(path, role, expected):
    assert _converter_for(path, role) == expected


@pytest.mark.asyncio
async def test_supporting_pdf_goes_through_pypdfium_without_extraction():
    doc = _file_document(file_path="/uploads/ref.pdf", file_type="application/pdf")

    with (
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="pdf text"),
        ) as convert_mock,
        patch(f"{MODULE}.replace_extracted_images", new=AsyncMock()) as replace_mock,
    ):
        result = await convert_file_document_to_markdown(doc, role=FileRole.SUPPORT)

    convert_mock.assert_awaited_once_with(
        "/uploads/ref.pdf", converter="pypdfium", keep_data_uris=False
    )
    replace_mock.assert_not_awaited()
    assert result.markdown == "pdf text"


@pytest.mark.asyncio
async def test_rasterized_temp_docx_is_used_and_removed(tmp_path):
    """When charts were rendered, the conversion and the display-size read
    both use the rasterized copy, which is deleted afterwards."""
    doc = _file_document(file_path="/uploads/abc.docx")
    rasterized_path = str(tmp_path / "rasterized.docx")
    with open(rasterized_path, "wb") as f:
        f.write(b"fake docx")

    with (
        patch(
            f"{MODULE}.rasterize_docx_drawings",
            new=AsyncMock(return_value=rasterized_path),
        ),
        patch(f"{MODULE}.replace_extracted_images", new=AsyncMock()),
        patch(
            f"{MODULE}.read_docx_image_display_sizes", return_value=None
        ) as sizes_mock,
        patch(
            f"{MODULE}.convert_to_markdown_fn",
            new=AsyncMock(return_value="# converted"),
        ) as convert_mock,
    ):
        await convert_file_document_to_markdown(doc)

    convert_mock.assert_awaited_once_with(
        rasterized_path, converter="markitdown", keep_data_uris=True
    )
    sizes_mock.assert_called_once_with(rasterized_path)
    assert not os.path.exists(rasterized_path)
