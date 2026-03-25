"""Unit tests for the admin logs router."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_log_dir(tmp_path: Path):
    """Context manager that points FILE_UPLOADS_MOUNT_PATH at *tmp_path*."""
    return patch(
        "api.routers.logs.env_config.FILE_UPLOADS_MOUNT_PATH",
        str(tmp_path),
    )


def _make_log_dir(tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


# ---------------------------------------------------------------------------
# _resolve_safe_path
# ---------------------------------------------------------------------------


def test_resolve_safe_path_valid_file(tmp_path):
    """A file that exists inside the log directory is returned."""
    from api.routers.logs import _resolve_safe_path

    log_dir = _make_log_dir(tmp_path)
    log_file = log_dir / "app.log"
    log_file.write_text("hello")

    with _patch_log_dir(tmp_path):
        result = _resolve_safe_path("app.log")

    assert result == log_file.resolve()


def test_resolve_safe_path_dot_dot_traversal(tmp_path):
    """Classic ../ traversal is rejected with 400."""
    from api.routers.logs import _resolve_safe_path

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_safe_path("../../../etc/passwd")

    assert exc_info.value.status_code == 400


def test_resolve_safe_path_sibling_dir_bypass(tmp_path):
    """A path escaping into a sibling directory is rejected with 400.

    This is the specific case that broke the old str.startswith() check:
    if log_dir is /uploads/logs, a candidate at /uploads/logs-evil/secret
    would pass startswith('/uploads/logs') but is correctly rejected by
    is_relative_to().
    """
    from api.routers.logs import _resolve_safe_path

    _make_log_dir(tmp_path)

    # Create the sibling directory and a file inside it to ensure the path
    # exists — the old code would only catch this via a 404 (file not found),
    # not via the traversal guard.
    evil_dir = tmp_path / "logs-evil"
    evil_dir.mkdir()
    (evil_dir / "secret").write_text("sensitive")

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_safe_path("../logs-evil/secret")

    assert exc_info.value.status_code == 400


def test_resolve_safe_path_absolute_path_rejected(tmp_path):
    """An absolute path as filename is rejected with 400.

    Python's Path joining replaces the base when the right operand is absolute,
    e.g. Path('/a/b') / '/c/d' == Path('/c/d'). is_relative_to() must catch this.
    """
    from api.routers.logs import _resolve_safe_path

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_safe_path("/etc/passwd")

    assert exc_info.value.status_code == 400


def test_resolve_safe_path_nonexistent_file_raises_404(tmp_path):
    """A filename that stays within the log dir but does not exist returns 404."""
    from api.routers.logs import _resolve_safe_path

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _resolve_safe_path("app.log.2024-01-01")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# _list_log_files
# ---------------------------------------------------------------------------


def test_list_log_files_missing_dir_returns_empty(tmp_path):
    """Returns an empty list when the logs directory does not exist."""
    from api.routers.logs import _list_log_files

    with _patch_log_dir(tmp_path):
        result = _list_log_files()

    assert result == []


def test_list_log_files_filters_non_app_log_files(tmp_path):
    """Only files whose names start with 'app.log' are returned."""
    from api.routers.logs import _list_log_files

    log_dir = _make_log_dir(tmp_path)
    (log_dir / "app.log").write_text("current")
    (log_dir / "app.log.2024-01-01").write_text("rotated")
    (log_dir / "error.log").write_text("should be ignored")
    (log_dir / "README.txt").write_text("also ignored")

    with _patch_log_dir(tmp_path):
        result = _list_log_files()

    names = {f.name for f in result}
    assert "app.log" in names
    assert "app.log.2024-01-01" in names
    assert "error.log" not in names
    assert "README.txt" not in names


def test_list_log_files_sorted_newest_first(tmp_path):
    """Files are returned sorted by modification time, newest first."""
    from api.routers.logs import _list_log_files

    log_dir = _make_log_dir(tmp_path)

    oldest = log_dir / "app.log.2024-01-01"
    oldest.write_text("old")
    oldest.touch()
    time.sleep(0.02)

    middle = log_dir / "app.log.2024-06-01"
    middle.write_text("middle")
    middle.touch()
    time.sleep(0.02)

    newest = log_dir / "app.log"
    newest.write_text("new")
    newest.touch()

    with _patch_log_dir(tmp_path):
        result = _list_log_files()

    assert [f.name for f in result] == ["app.log", "app.log.2024-06-01", "app.log.2024-01-01"]


# ---------------------------------------------------------------------------
# list_logs endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_logs_returns_empty_list(tmp_path):
    """Returns an empty list when no log files exist."""
    from api.routers.logs import list_logs

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        result = await list_logs()

    assert result == []


@pytest.mark.asyncio
async def test_list_logs_returns_correct_metadata(tmp_path):
    """Returns LogFileInfo with the correct filename, size, and mtime."""
    from api.routers.logs import list_logs

    log_dir = _make_log_dir(tmp_path)
    log_file = log_dir / "app.log"
    log_file.write_text("log content")

    with _patch_log_dir(tmp_path):
        result = await list_logs()

    assert len(result) == 1
    info = result[0]
    assert info.filename == "app.log"
    assert info.size_bytes == log_file.stat().st_size
    assert info.modified_at is not None


@pytest.mark.asyncio
async def test_list_logs_multiple_files_newest_first(tmp_path):
    """Multiple log files are listed newest first."""
    from api.routers.logs import list_logs

    log_dir = _make_log_dir(tmp_path)
    (log_dir / "app.log.2024-01-01").write_text("old")
    time.sleep(0.02)
    (log_dir / "app.log").write_text("new")

    with _patch_log_dir(tmp_path):
        result = await list_logs()

    assert result[0].filename == "app.log"
    assert result[1].filename == "app.log.2024-01-01"


# ---------------------------------------------------------------------------
# download_log endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_log_returns_file_response(tmp_path):
    """A valid log file download returns a FileResponse with correct attributes."""
    from api.routers.logs import download_log

    log_dir = _make_log_dir(tmp_path)
    log_file = log_dir / "app.log"
    log_file.write_text("log line 1\nlog line 2\n")

    with _patch_log_dir(tmp_path):
        response = await download_log(filename="app.log")

    assert isinstance(response, FileResponse)
    assert response.media_type == "text/plain"
    assert response.headers["content-disposition"] == 'attachment; filename="app.log"'


@pytest.mark.asyncio
async def test_download_log_traversal_raises_400(tmp_path):
    """A path traversal attempt raises HTTP 400."""
    from api.routers.logs import download_log

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            await download_log(filename="../../../etc/passwd")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_download_log_nonexistent_raises_404(tmp_path):
    """A valid-looking but absent filename raises HTTP 404."""
    from api.routers.logs import download_log

    _make_log_dir(tmp_path)

    with _patch_log_dir(tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            await download_log(filename="app.log.2099-01-01")

    assert exc_info.value.status_code == 404
