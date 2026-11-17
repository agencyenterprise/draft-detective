"""TUS uploads leave nothing behind in the router's working directory.

A finished upload's data file moves to permanent storage, and the completion hook
removes its ``.info``. Whatever an abandoned upload leaves is swept once it is old,
each time an upload is created.
"""

import base64
import os
import time
import uuid
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.api.auth import get_current_user
from lib.api.routers.tus_upload import (
    TUS_WORKING_DIR,
    _get_pre_create_hook,
    tus_router,
)
from lib.models.project import Project
from lib.models.user import User
from lib.services.files.tus_cleanup import remove_upload_info, sweep_working_dir

MODULE = "lib.api.routers.tus_upload"
TUS = {"Tus-Resumable": "1.0.0"}
PROJECT = Project(
    id=uuid.uuid4(), title="Test", user_id=uuid.uuid4(), current_revision=1
)
THREE_DAYS_AGO = time.time() - 3 * 24 * 3600


async def _accept(metadata: dict, upload_info: dict) -> None:
    """The project checks are covered elsewhere; any upload may start here."""


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(tus_router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid.uuid4(), email="someone@example.com"
    )
    app.dependency_overrides[_get_pre_create_hook] = lambda: _accept
    with TestClient(app) as test_client:
        yield test_client


def test_a_finished_upload_leaves_no_info_file(client: TestClient) -> None:
    body = b"%PDF-1.4 a small document"
    created = client.post(
        "/tus",
        headers={
            **TUS,
            "Upload-Length": str(len(body)),
            "Upload-Metadata": "project_id "
            + _b64(str(PROJECT.id))
            + ",filename "
            + _b64("a.pdf"),
        },
    )
    assert created.status_code == 201, created.text
    upload_id = created.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    data_path = os.path.join(TUS_WORKING_DIR, upload_id)
    assert os.path.exists(data_path + ".info")

    finalize = AsyncMock(side_effect=_move_to_storage)
    with (
        patch(f"{MODULE}.get_project_access", AsyncMock(return_value=(PROJECT, None))),
        patch(f"{MODULE}.finalize_file_from_path", finalize),
    ):
        patched = client.patch(
            f"/tus/{upload_id}",
            headers={
                **TUS,
                "Upload-Offset": "0",
                "Content-Type": "application/offset+octet-stream",
            },
            content=body,
        )

    assert patched.status_code == 204, patched.text
    finalize.assert_awaited_once()
    assert not os.path.exists(data_path)
    assert not os.path.exists(data_path + ".info")


@pytest.mark.asyncio
async def test_a_failed_info_removal_does_not_fail_the_upload(tmp_path) -> None:
    info = tmp_path / "upload.info"
    info.write_bytes(b"{}")
    with patch(
        "lib.services.files.tus_cleanup.aiofiles.os.remove",
        AsyncMock(side_effect=PermissionError),
    ):
        await remove_upload_info(str(tmp_path / "upload"))

    assert info.exists()


@pytest.mark.asyncio
async def test_creating_an_upload_sweeps_the_working_dir() -> None:
    user = User(id=uuid.uuid4(), email="someone@example.com")
    handler = _get_pre_create_hook(current_user=user)
    with (
        patch(f"{MODULE}.get_project_access", AsyncMock(return_value=(PROJECT, None))),
        patch(f"{MODULE}.sweep_working_dir", AsyncMock()) as sweep,
    ):
        await handler({"project_id": str(PROJECT.id)}, {})

    sweep.assert_awaited_once_with(TUS_WORKING_DIR)


@pytest.mark.asyncio
async def test_sweep_removes_old_files_and_keeps_recent_ones(tmp_path) -> None:
    working_dir = tmp_path / "tus"
    locks = working_dir / ".locks"
    locks.mkdir(parents=True)
    abandoned = uuid.uuid4().hex
    old = [
        working_dir / abandoned,
        working_dir / f"{abandoned}.info",
        working_dir / f"{uuid.uuid4().hex}.info",  # a finished upload's, before the fix
        locks / f"{abandoned}.lock",
    ]
    in_progress = uuid.uuid4().hex
    recent = [
        working_dir / in_progress,
        working_dir / f"{in_progress}.info",
        locks / f"{in_progress}.lock",
    ]
    # Outside the working directory: a stored document in the mount root
    stored = tmp_path / f"{'a' * 32}.pdf"
    for path in [*old, *recent, stored]:
        path.write_bytes(b"x")
    for path in [*old, stored]:
        os.utime(path, (THREE_DAYS_AGO, THREE_DAYS_AGO))

    removed = await sweep_working_dir(str(working_dir))

    assert removed == len(old)
    assert [p for p in old if p.exists()] == []
    assert all(p.exists() for p in recent)
    assert stored.exists()
    assert locks.is_dir()


@pytest.mark.asyncio
async def test_sweep_of_a_missing_dir_removes_nothing(tmp_path) -> None:
    assert await sweep_working_dir(str(tmp_path / "tus")) == 0


def _b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


async def _move_to_storage(file_path: str, **_: object) -> tuple[MagicMock, bool]:
    """Stand-in for ``finalize_file_from_path``: the data file leaves the directory."""
    os.remove(file_path)
    return MagicMock(), False
