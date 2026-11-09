"""Every soffice run is kept off the network and away from a document's links.

The real LibreOffice behaviour is proven in
``tests/integration/docx/test_libreoffice_links.py``; these check that both
places that start soffice hand it the locked-down profile and environment.
"""

import asyncio
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.services.converters.docx_preprocessor import docx_preprocessor
from lib.services.converters.libreoffice_profile import (
    locked_down_profile,
    soffice_env,
)
from lib.services.docx import drawing_rasterization

_OOR = "{http://openoffice.org/2001/registry}"
_PROFILE = re.compile(r"^-env:UserInstallation=file://")
_INET = "/org.openoffice.Inet/Settings"
_BLOCK_LINKS = (
    "/org.openoffice.Office.Common/Security/Scripting/BlockUntrustedRefererLinks"
)


def _settings(profile_dir: Path) -> dict[str, str]:
    """``path/name -> value`` for every setting the profile seeds."""
    registry_file = profile_dir / "user" / "registrymodifications.xcu"
    if not registry_file.exists():
        return {}
    settings = {}
    for item in ET.parse(registry_file).getroot():
        for prop in item:
            key = f"{item.get(f'{_OOR}path')}/{prop.get(f'{_OOR}name')}"
            settings[key] = prop.findtext("value") or ""
    return settings


def _is_locked_down(profile_dir: Path) -> bool:
    settings = _settings(profile_dir)
    return (
        settings.get(_BLOCK_LINKS) == "true"
        and settings.get(f"{_INET}/ooInetProxyType") == "2"
        and settings.get(f"{_INET}/ooInetHTTPProxyName", "").endswith(".invalid")
        and settings.get(f"{_INET}/ooInetHTTPSProxyName", "").endswith(".invalid")
        and settings.get(f"{_INET}/ooInetNoProxy") == ""
    )


class _Soffice:
    """Stands in for soffice: records how it was started, then exits."""

    def __init__(self, output_name: str) -> None:
        self.output_name = output_name
        self.locked_down: bool | None = None
        self.env: dict[str, str] | None = None

    async def __call__(self, *args: str, **kwargs: Any) -> MagicMock:
        profile = next(a for a in args if a.startswith("-env:UserInstallation="))
        self.locked_down = _is_locked_down(Path(_PROFILE.sub("", profile)))
        self.env = kwargs.get("env")
        outdir = Path(args[args.index("--outdir") + 1])
        (outdir / self.output_name).write_bytes(b"converted")
        process = MagicMock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        return process


@pytest.fixture
def proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_PROXY", "10.0.0.0/8,.svc.cluster.local")
    monkeypatch.setenv("https_proxy", "http://egress.example:3128")
    monkeypatch.setenv("LANG", "en_US.UTF-8")


def test_profile_is_locked_down(tmp_path: Path) -> None:
    argument = locked_down_profile(tmp_path / "profile")

    assert argument == f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}"
    assert _is_locked_down(tmp_path / "profile")


def test_soffice_env_drops_only_proxy_settings(proxy_environment: None) -> None:
    env = soffice_env()

    assert "NO_PROXY" not in env
    assert "https_proxy" not in env
    assert env["LANG"] == "en_US.UTF-8"


@pytest.mark.asyncio
async def test_doc_conversion_is_locked_down(
    tmp_path: Path, proxy_environment: None
) -> None:
    doc = tmp_path / "upload.doc"
    doc.write_bytes(b"\xd0\xcf\x11\xe0")
    soffice = _Soffice("upload.docx")

    with (
        patch.object(shutil, "which", return_value="/usr/bin/soffice"),
        patch.object(asyncio, "create_subprocess_exec", soffice),
    ):
        await docx_preprocessor.convert_doc_to_docx(str(doc))

    assert soffice.locked_down is True
    assert soffice.env is not None and "NO_PROXY" not in soffice.env


@pytest.mark.asyncio
async def test_drawing_render_is_locked_down(
    tmp_path: Path, proxy_environment: None
) -> None:
    soffice = _Soffice("render-source.pdf")

    with (
        patch.object(shutil, "which", return_value="/usr/bin/soffice"),
        patch.object(asyncio, "create_subprocess_exec", soffice),
        patch.object(
            drawing_rasterization, "_write_render_source_docx", return_value=1
        ),
        patch.object(
            drawing_rasterization, "_render_pdf_pages", return_value=["page.png"]
        ),
    ):
        rendered = await drawing_rasterization._render_drawings_to_images(
            str(tmp_path / "in.docx"), [(914400, 914400)]
        )

    assert rendered is not None
    shutil.rmtree(rendered[0])
    assert soffice.locked_down is True
    assert soffice.env is not None and "NO_PROXY" not in soffice.env
