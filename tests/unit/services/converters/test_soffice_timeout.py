"""A soffice run that times out or is cancelled leaves no LibreOffice running.

On Linux ``soffice`` is a launcher: it starts ``soffice.bin``, which does the
conversion, as its child. Killing only the launcher left ``soffice.bin`` running
at full CPU after the caller had given up, one more for every upload of a
document slow enough to time out. A fake launcher stands in for soffice here: it
starts a long-running child and records its pid.
"""

import asyncio
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from lib.services.converters.docx_preprocessor import DocxPreprocessor
from lib.services.docx import drawing_rasterization


@pytest.fixture
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake ``soffice`` whose converter child outlives it unless its group dies.

    Returns the file the child's pid is written to.
    """
    pid_file = tmp_path / "converter.pid"
    script = tmp_path / "soffice"
    script.write_text(
        '#!/bin/sh\nsleep 60 </dev/null >/dev/null 2>&1 &\necho $! > "$CONVERTER_PID_FILE"\nwait\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("CONVERTER_PID_FILE", str(pid_file))
    monkeypatch.setattr(shutil, "which", lambda name: str(script))
    return pid_file


def _running(pid: int) -> bool:
    """Whether ``pid`` is alive (a zombie awaiting its reaper counts as gone)."""
    state = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()
    return bool(state) and not state.startswith("Z")


async def _converter_pid(pid_file: Path) -> int:
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text().strip():
            return int(pid_file.read_text())
        await asyncio.sleep(0.05)
    raise AssertionError("the fake soffice never started its converter")


def _assert_stops(pid: int) -> None:
    deadline = time.monotonic() + 5
    while _running(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _running(pid), "soffice.bin outlived the timed-out conversion"


@pytest.mark.asyncio
async def test_doc_conversion_timeout_stops_the_converter(
    tmp_path: Path, launcher: Path
) -> None:
    doc = tmp_path / "upload.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")

    with (
        patch.object(DocxPreprocessor, "CONVERSION_TIMEOUT", 0.5),
        pytest.raises(RuntimeError, match="timed out"),
    ):
        await DocxPreprocessor().convert_doc_to_docx(str(doc))

    _assert_stops(await _converter_pid(launcher))


@pytest.mark.asyncio
async def test_drawing_render_timeout_stops_the_converter(
    tmp_path: Path, launcher: Path
) -> None:
    with (
        patch.object(drawing_rasterization, "_RENDER_TIMEOUT", 0.5),
        patch.object(
            drawing_rasterization, "_write_render_source_docx", return_value=1
        ),
    ):
        rendered = await drawing_rasterization._render_drawings_to_images(
            str(tmp_path / "in.docx"), [(914400, 914400)]
        )

    assert rendered is None
    _assert_stops(await _converter_pid(launcher))


@pytest.mark.asyncio
async def test_cancelled_conversion_stops_the_converter(
    tmp_path: Path, launcher: Path
) -> None:
    doc = tmp_path / "upload.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    task = asyncio.create_task(DocxPreprocessor().convert_doc_to_docx(str(doc)))
    pid = await _converter_pid(launcher)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    _assert_stops(pid)


@pytest.mark.asyncio
async def test_cancel_while_soffice_is_starting_stops_the_converter(
    tmp_path: Path, launcher: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancellation can land after the launcher has started but before
    ``create_subprocess_exec`` returns it (while asyncio connects its pipes)."""
    spawn = asyncio.create_subprocess_exec

    async def slow_spawn(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await spawn(*args, **kwargs)
        await asyncio.sleep(3)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_spawn)
    doc = tmp_path / "upload.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    task = asyncio.create_task(DocxPreprocessor().convert_doc_to_docx(str(doc)))
    pid = await _converter_pid(launcher)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    _assert_stops(pid)
